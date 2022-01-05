from sip import SIPSession
import db,config
import time,os
import xml.etree.ElementTree as ET
import sys,socket,time,re,datetime
import sqlite3,logging
import db_service

logging.basicConfig(filename='service_log.txt', level=logging.ERROR)

VOIP_NEW = 0

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
class SipListener:
    def start(self):
        self.config = db_service.load_config()
        hostname = socket.gethostname()
        local_ip = socket.gethostbyname(hostname)
        sip_session = SIPSession(local_ip,self.config['sip_login'],self.config['sip_ip'],self.config['sip_password'],account_port=5060,display_name="mikran")
        sip_session.call_ringing += self.voip_ringing
        sip_session.call_bad_request += self.voip_badrequest
        sip_session.send_sip_register()
        
    def voip_badrequest(self,session,data):
        self.start()

    def voip_ringing(self,session,data):
        print("------------ RINGING START")
        print(data)
        print("RINGING STOP --------------")
        
        try:
            call_id = re.findall(r'Call-ID: (.*?)\r\n', data)
            call_id = call_id[0]
            call_to = re.findall(r'To: (.*?)\r\n', data)
            call_to = call_to[0]
            call_from = re.findall(r'From: (.*?)\r\n', data)
            call_from = call_from[0]
            calling_number = re.findall(r'sip:([0-9]+)', call_from)
            calling_number = calling_number[0]
            print("Number calling: ",calling_number)
        
            unix_time = int(time.time())
            sql = "INSERT INTO voip_calls (call_id,start_time,calling_number,call_to,call_from,call_received,start_time_unix) VALUES ('%s','%s','%s','%s','%s','%s','%s')" % (call_id,datetime.datetime.now().strftime("%m-%d-%Y, %H:%M:%S"),calling_number,call_to,call_from,0,unix_time)

            print(sql)
            db_service.execute(sql)
                        
        except Exception as e:
            print(str(e))

if __name__ == "__main__":
    db_service.init_db()
    listener = SipListener()
    listener.start()
    #app = SilicanHistoryThread()
    #app.run()
