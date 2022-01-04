import db,config
import time,os
import xml.etree.ElementTree as ET
import sys,socket,time
from datetime import datetime
import sqlite3,logging
from sip import SIPSession

logging.basicConfig(filename='service_log.txt', level=logging.ERROR)

class SilicanThreadBase:
    
    def connect(self):
        self.config = db.load_config()
        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock.settimeout(10)
            self.sock.connect((self.config['silican_address'],self.config['silican_port']))
            self.sock.settimeout(None)
        except socket.timeout as e:
            pass
        except socket.error as e:
            pass
            #raise

    def sendall(self,message):
        try:
            self.sock.sendall(message)
        except Exception as e:
            logging.error("connect() : ", exc_info=True)

    def login(self):
        message = '<XCTIP><Log><MakeLog><CId>12</CId><Login>%s</Login><Pass>%s</Pass></MakeLog></Log></XCTIP>' % (self.config['login'],self.config['password'])
        self.sendall(message.encode('UTF-8'))

    def read_frame(self):
        self.parser.feed("<root>")

        while True:
            try:
                data = self.sock.recv(1)
                data = data.decode("utf-8")
                self.parser.feed(data)
                for event, elem in self.parser.read_events():
                    if elem.tag == 'XCTIP':
                        #print("READ FRAME",elem)
                        ET.dump(elem)
                        return elem
            except ET.ParseError as e:
                pass
class SipLoger:
    def register(self):
        hostname = socket.gethostname()
        local_ip = socket.gethostbyname(hostname)
        sip_session = SIPSession(local_ip,self.config['sip_login'],self.config['sip_ip'],self.config['sip_password'],account_port=5060,display_name="mikran")
        sip_session.call_ringing += self.voip_ringing
        sip_session.call_bad_request += self.voip_badrequest
        sip_session.send_sip_register()
        
    def voip_badrequest(self,session,data):
        pass

    def voip_ringing(self,session,data):
        pass

if __name__ == "__main__":
    app = SilicanHistoryThread()
    app.run()
