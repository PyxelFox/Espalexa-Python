import math
from uuid import getnode as get_mac
import socket
import struct
from http.server import BaseHTTPRequestHandler, HTTPServer
import threading
import time
import datetime

class EspalexaDevice:
	def __init__(self, deviceName, gnCallback, hasColor, initialValue = 0):
		self.deviceName = deviceName
		self.callback = gnCallback
		self.val = initialValue
		self.val_last = self.val
		self.hasColor = hasColor
		self.sat = 0
		self.hue = 0
		self.ct = 0
		self.changed = 0

	def isColorDevice(self):
		return self.hasColor
		
	def isColorTemperatureMode(self):
		return bool(self.ct)
		
	def getName(self):
		return self.deviceName
		
	def getLastChangedProperty(self):
		return self.changed
		
	def getValue(self):
		return self.val
		
	def getHue(self):
		return self.hue
		
	def getSat(self):
		return self.sat
		
	def getCt(self):
		if (self.ct == 0):
			return 500
		return self.ct
		
	def getColorRGB(self):
		rgb = []
		
		if (self.isColorTemperatureMode()):
			temp = float(10000/self.ct)
			r, g, b = (0, 0, 0)
			
			if (temp <= 66):
				r = 255
				g = temp
				g = float(99.470802 * math.log(g) - 161.119568)
				if (temp <= 19):
					b = 0
				else:
					b = temp - 10
					b = float(138.517731 * math.log(b) - 305.044793)
			else:
				r = temp - 60
				r = float(329.698727 * math.pow(r, -0.13320476))
				g = temp - 60
				g = 288.12217 * math.pow(g, -0.07551485)
				b = 255
			r = max(min(r, 255.1), 0.1)
			g = max(min(g, 255.1), 0.1)
			b = max(min(b, 255.1), 0.1)
			rgb = [r, g, b]
		else: #hue + sat mode
			h = float(float(self.hue) / 65525.0)
			s = float(float(self.sat) / 255.0)
			i = float(math.floor(float(h * 6)))
			f = float(h * 6 - i)
			p = float(255 * (1 - s))
			q = float(255 * (1 - f * s))
			t = float(255 * (1 - ( 1 - f) * s))
			switch = i % 6
			if switch == 0:
				rgb = [255, t, p]
			elif switch == 1:
				rgb = [q, 255, p]
			elif switch == 2:
				rgb = [p, 255, t]
			elif switch == 3:
				rgb = [p, q, 255]
			elif switch == 4:
				rgb = [t, p, 255]
			elif switch == 5:
				rgb = [255, p, q]
		return ((int(rgb[0]) << int(16)) | (int(rgb[1]) << int(8)) | (int(rgb[2])))
		
	def getLastValue(self):
		if (self.val_last == 0):
			return 255
		return self.val_last
	
	def setPropertyChanged(self, p):
		#0: initial 1: on 2: off 3: bri 4: col 5: ct
		self.changed = p
		
	def setName(self, name):
		self.deviceName = name
		
	def setValue(self, val):
		if not (self.val == 0):
			self.val_last = self.val
		if not (val == 0):
			self.val_last = val
		self.val = val
		
	def setPercent(self, perc):
		val = perc * 255
		val = int(val / 100)
		if (val > 255):
			val = 255
		self.setValue(val)
		
	def setColor(self, hue, sat):
		self.hue = hue
		self.sat = sat
		self.ct = 0
		
	def setColorCT(self, ct):
		self.ct = ct
		
	def doCallback(self):
		if (self.hasColor):
			self.callback(self.val, self.getColorRGB())
		else:
			self.callback(self.val)
			
class Espalexa:
	def __init__(self, MAXDEVICES = 10, DEBUG = False):
		self.currentDeviceCount = 0
		self.ufpConnected = False
		self.escapedMac = ""
		self.devices = []
		self.startTime = 0
		self.MCAST_GRP = '239.255.255.250'
		self.MCAST_PORT = 1900
		self.MAXDEVICES = MAXDEVICES
		self.DEBUG = DEBUG
		
	#device JSON string: color+temperature device emulates LCT015, dimmable device LWB010, (TODO: on/off Plug 01, color temperature device LWT010, color device LST001)
	def deviceJsonString(self, deviceId):
		if (deviceId < 1) or (deviceId > self.currentDeviceCount):
			return "{}"
		dev = self.devices[deviceId - 1]
		json = "{\"type\":\""
		if dev.isColorDevice():
			json = json + "Extended color light"
		else:
			json = json + "Dimmable light"
		json = json + "\",\"manufacturername\":\"OpenSource\",\"swversion\":\"0.1\",\"name\":\""
		json = json + dev.getName()
		mac = ':'.join(("%012X" % get_mac())[i:i+2] for i in range(0, 12, 2))
		json = json + "\",\"uniqueid\":\"" + mac + "-" + str(deviceId + 1)
		json = json + "\",\"modelid\":\""
		if dev.isColorDevice():
			json = json + "LCT015"
		else:
			json = json + "LWB010"
		json = json + "\",\"state\":{\"on\":"
		json = json + str(dev.getValue()) + ",\"bri\":" + str(dev.getLastValue() - 1)
		if dev.isColorDevice():
			json = json + ",\"xy\":[0.00000,0.00000],\"colormode\":\"";
			if dev.isColorTemperatureMode():
				json = json + "ct"
			else:
				json = json + "hs"
			json += "\",\"effect\":\"none\",\"ct\":" + str(dev.getCt()) + ",\"hue\":" + str(dev.getHue()) + ",\"sat\":" + str(dev.getSat());
		json = json + ",\"alert\":\"none\",\"reachable\":true}}"
		return json
		
	class httpHandler(BaseHTTPRequestHandler):
		outer = None	
		def do_GET(self):
			path = str(self.path)
			if (path == "/espalexa"):
				self.outer.servePage(self)
				return
			elif (path == "/description.xml"):
				self.outer.serveDescription(self)
				return
			elif (path.startswith("/api")):
				content_len = int(self.headers.get('Content-Length', 0))
				post_body = self.rfile.read(content_len)
				self.outer.handleAlexaApiCall(path, post_body.decode('utf-8'), self)
				return
			else:
				if (self.outer.DEBUG):
					print("Not-Found HTTP call:")
					print("URI: " + path)
					content_len = int(self.headers.get('Content-Length', 0))
					post_body = self.rfile.read(content_len)
					print("Body: " + str(post_body))
				self.send_response(200)
				self.send_header('Content-type', 'text/html')
				self.end_headers()
				self.wfile.write(("Not Found (espalexa-internal)").encode('utf-8'))
				return
			self.send_response(200)
			self.send_header('Content-type', 'text/html')
			self.end_headers()
			self.wfile.write(("ERROR").encode('utf-8'))
			return
			
		def do_PUT(self):
			path = str(self.path)
			if (path.startswith("/api")):
				content_len = int(self.headers.get('Content-Length', 0))
				post_body = self.rfile.read(content_len)
				self.outer.handleAlexaApiCall(path, post_body.decode('utf-8'), self)
			
	def servePage(self, handler):
		if (self.DEBUG):
			print("HTTP Req espalexa...")
		res = "Hello from Espalexa!\r\n\r\n"
		for i in range(self.currentDeviceCount):
			res = res + "Value of device " + str(i + 1) + " (" + self.devices[i].getName() + "): " + str(self.devices[i].getValue()) + "\r\n"
		t = datetime.datetime.now() - self.startTime
		t = t.total_seconds()
		td = divmod(t, 86400)
		th = divmod(td[0], 3600)
		tm = divmod(th[0], 60)
		ts = divmod(tm[0], 1)
		#TO-DO: add uptime here
		res += "\r\nUptime: %d days, %d hours, %d minutes and %d seconds" % (td[0], th[0], tm[0], ts[0])
		res += "\r\n\r\nEspalexa library v2.3.4 by Christian Schwinne 2019"
		handler.send_response(200)
		handler.send_header('Content-type', 'text/plain')
		handler.end_headers()
		handler.wfile.write(res.encode('utf-8'))
		
	def serveDescription(self, handler):
		if (self.DEBUG):
			print("# Responding to description.xml ... #")
		localIP = self.get_ip()
		setup_xml = """<?xml version=\"1.0\" ?>
		<root xmlns=\"urn:schemas-upnp-org:device-1-0\">
		<specVersion><major>1</major><minor>0</minor></specVersion>
		<URLBase>http://%s:80/</URLBase>
		<device>
		  <deviceType>urn:schemas-upnp-org:device:Basic:1</deviceType>
		  <friendlyName>Espalexa (%s)</friendlyName>
		  <manufacturer>Royal Philips Electronics</manufacturer>
		  <manufacturerURL>http://www.philips.com</manufacturerURL>
		  <modelDescription>Philips hue Personal Wireless Lighting</modelDescription>
		  <modelName>Philips hue bridge 2012</modelName>
		  <modelNumber>929000226503</modelNumber>
		  <modelURL>http://www.meethue.com</modelURL>
		  <serialNumber>%s</serialNumber>
		  <UDN>uuid:2f402f80-da50-11e1-9b23-%s</UDN>
		  <presentationURL>index.html</presentationURL>
		  <iconList>
			<icon>
			  <mimetype>image/png</mimetype>
			  <height>48</height>
			  <width>48</width>
			  <depth>24</depth>
			  <url>hue_logo_0.png</url>
			</icon>
		  </iconList>
		</device>
		</root>	
		""" % (str(localIP), str(localIP), hex(get_mac())[2:], hex(get_mac())[2:])
		if (self.DEBUG):
			print("Sending: " + setup_xml)
		handler.send_response(200)
		handler.send_header('Content-type', 'application/xml')
		handler.end_headers()
		handler.wfile.write(setup_xml.encode('utf-8'))
	
	def startHttpServer(self):
		self.httpHandler.outer = self
		self.server = HTTPServer(('', 80), self.httpHandler)
		tServer = threading.Thread(target = self.server.serve_forever)
		tServer.daemon = True
		tServer.start()
	
	#called when Alexa sends ON command
	def alexaOn(self, deviceId):
		self.devices[deviceId - 1].setValue(self.devices[deviceId - 1].getLastValue())
		self.devices[deviceId - 1].setPropertyChanged(1)
		self.devices[deviceId - 1].doCallback()

	#called when Alexa sends OFF command
	def alexaOff(self, deviceId):
		self.devices[deviceId - 1].setValue(0)
		self.devices[deviceId - 1].setPropertyChanged(2)
		self.devices[deviceId - 1].doCallback()

	#called when Alexa sends BRI command
	def alexaDim(self, deviceId, briL):
		if (briL == 255):
			self.devices[deviceId - 1].setValue(255)
		else:
			self.devices[deviceId - 1].setValue(briL + 1)
		self.devices[deviceId - 1].setPropertyChanged(3)
		self.devices[deviceId - 1].doCallback()
		
	#called when Alexa sends HUE command
	def alexaCol(self, deviceId, hue, sat):
		self.devices[deviceId - 1].setColor(hue, sat)
		self.devices[deviceId - 1].setPropertyChanged(4)
		self.devices[deviceId - 1].doCallback()
		
	#called when Alexa sends CT command (color temperature)
	def alexaCt(self, deviceId, ct):
		self.devices[deviceId - 1].setColorCT(ct)
		self.devices[deviceId - 1].setPropertyChanged(5)
		self.devices[deviceId - 1].doCallback()
	
	#used to get local IP
	def get_ip(self):
		s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
		try:
			#doesn't even have to be reachable
			s.connect(('10.255.255.255', 1))
			IP = s.getsockname()[0]
		except:
			IP = '127.0.0.1'
		finally:
			s.close()
		return IP

	#respond to UDP SSDP M-SEARCH
	def respondToSearch(self, request_addr):
		localIP = self.get_ip()
		response = "HTTP/1.1 200 OK\r\n" + "EXT:\r\n" + "CACHE-CONTROL: max-age=100\r\n" + "LOCATION: http://" + localIP + ":80/description.xml\r\n" + "SERVER: FreeRTOS/6.0.5, UPnP/1.0, IpBridge/1.17.0\r\n" + "hue-bridgeid: " + str(hex(get_mac())) + "\r\n" + "ST: urn:schemas-upnp-org:device:basic:1\r\n" + "USN: uuid:2f402f80-da50-11e1-9b23-" + str(hex(get_mac())) + "::upnp:rootdevice\r\n" + "\r\n"
		ip, port = request_addr
		self.udp.sendto(response.encode('utf-8'), (ip, port))
		
	def begin(self):
		if (self.DEBUG):
			print("Espalexa Begin...")
			print("MAXDEVICES " + str(self.MAXDEVICES))
		self.escapedMac = str(get_mac())
		# setup the udp multicast receiver here
		self.udp = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
		self.udp.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
		self.udp.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 32) 
		self.udp.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_LOOP, 1)
		self.udp.bind((self.MCAST_GRP, self.MCAST_PORT))
		host = socket.gethostbyname(socket.gethostname())
		self.udp.setsockopt(socket.SOL_IP, socket.IP_MULTICAST_IF, socket.inet_aton(host))
		mreq = struct.pack("4sl", socket.inet_aton(self.MCAST_GRP), socket.INADDR_ANY)
		self.udp.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)
		self.udpConnected = True
		self.startTime = datetime.datetime.now()
		if (self.udpConnected):
			self.startHttpServer()
			if (self.DEBUG):
				print("Done")
			return True
		if (self.DEBUG):
			print("Failed")
		return False
		
	def loop(self):
		#TO-DO (solved): http server handle stuff -> serve_forever() does this -> no need here
		
		if not (self.udpConnected):
			return
		#loop pause until data is received
		request, request_addr = self.udp.recvfrom(1024)
		request = request.decode('utf-8')
		#if (self.DEBUG):
		#	print(request)
		if (request):
			if (request.find("M-SEARCH") >= 0):
				if (request.find("upnp:rootdevice") > 0) or (request.find("asic:1") > 0):
					if (self.DEBUG):
						print(request)
						print("Responding search req...")
					self.respondToSearch(request_addr)
	
	def addDevice(self, deviceName, callback, hasColor, initialValue = 0):
		if (self.currentDeviceCount >= self.MAXDEVICES):
			return False
		if (self.DEBUG):
			print("Adding device")
		self.devices.append(EspalexaDevice(deviceName, callback, hasColor, initialValue))
		self.currentDeviceCount = self.currentDeviceCount + 1
		return True	
	
	def handleAlexaApiCall(self, req, body, handler):
		if (self.DEBUG):
			print("AlexaApiCall")
			print(req)
			print(body)
		if (req.find("api") < 0):
			return False	#return if not an API call	
		print("- Is API call")
		if (self.DEBUG):
			print("Ok")
			
		if (body.find("devicetype") > 0): #client wants a hue api username, we dont care and give static			
			if (self.DEBUG):
				print("devType")
			print("-! USERNAME REQUEST")
			body = "";
			handler.send_response(200)
			handler.send_header('Content-type', 'application/json')
			handler.end_headers()
			handler.wfile.write(("[{\"success\":{\"username\": \"2WLEDHardQrI3WHYTHoMcXHgEspsM8ZZRpSKtBQr\"}}]").encode('utf-8'))
			return True
		print("- Checked USERNAME request")
			
		if (req.find("state") > 0): #client wants to control light
			print("-! CONTROL REQUEST")
			handler.send_response(200)
			handler.send_header('Content-type', 'application/json')
			handler.end_headers()
			handler.wfile.write(("[{\"success\":true}]").encode('utf-8'))
			tempDeviceId = int(req[(req.find("lights") + 7):].split('/')[0])	
			if (self.DEBUG):
				print("ls" + str(tempDeviceId))
			if (body.find("false") > 0):
				self.alexaOff(tempDeviceId)
				return True
			if (body.find("bri") > 0):
				self.alexaDim(tempDeviceId, int(body[(body.find("bri") + 5):].split('}')[0]))
				return True
			if (body.find("hue") > 0):
				self.alexaCol(tempDeviceId, int(body[(body.find("hue") + 5):]), int(body[(body.find("sat") + 5):]))
				return True
			if (body.find("ct") > 0):
				self.alexaCt(tempDeviceId, int(body[(body.find("ct") + 4):].split('}')[0]))
				return True
			self.alexaOn(tempDeviceId)
			return True
		print("- Checked CONTROL request")
		
		pos = req.find("lights")
		if (pos > 0): #client wants light info
			print("-! LIGHTS REQUEST")
			tempDeviceId = req[(pos + 7):]
			if (tempDeviceId == ''):	#python won't convert '' into 0
				tempDeviceId = 0
			else:
				tempDeviceId = int(tempDeviceId)
			if (self.DEBUG):
				print("l" + str(tempDeviceId))
				
			if (tempDeviceId == 0): #client wants all lights				
				if (self.DEBUG):
					print("lAll")
				jsonTemp = "{"
				for i in range(self.currentDeviceCount):
					jsonTemp = jsonTemp + "\"" + str(i + 1) + "\":"
					jsonTemp = jsonTemp + self.deviceJsonString(i + 1)
					if (i < self.currentDeviceCount - 1):
						jsonTemp = jsonTemp + ","
				jsonTemp = jsonTemp + "}"
				handler.send_response(200)
				handler.send_header('Content-type', 'application/json')
				handler.end_headers()
				handler.wfile.write(jsonTemp.encode('utf-8'))
			else:
				handler.send_response(200)
				handler.send_header('Content-type', 'application/json')
				handler.end_headers()
				handler.wfile.write(self.deviceJsonString(tempDeviceId).encode('utf-8'))
			return True
		print("- Checked LIGHTS request")
		handler.send_response(200)
		handler.send_header('Content-type', 'application/json')
		handler.end_headers()
		handler.wfile.write(("{}").encode('utf-8'))
		print("- ERROR")
		return True
	
	def getEscapedMac(self):
		return self.escapedMac
		
	def toPercent(self, bri):
		perc = bri*100
		return int(perc/255)
	
def testCallback(brightness, rgb):
	print("Brightness: " + str(brightness))
	print("Red: " + str((rgb >> 16) & 0xFF) + ", Green: " + str((rgb >> 8) & 0xFF) + ", Blue: " + str(rgb & 0xFF))
		
def loop(espalexa):
	while True:
		espalexa.loop()
			
if __name__ == "__main__":
	espalexa = Espalexa(MAXDEVICES = 5, DEBUG = True)
	espalexa.addDevice("PythonLight", testCallback, True)
	espalexa.addDevice("Fernseher", testCallback, True)
	espalexa.begin()			
	t = threading.Thread(target = loop, args = (espalexa,))
	t.daemon = True
	t.start()
	while True:
		print(".")
		time.sleep(60)
			
			
			
			
			
			
			
			
