from sip import SIPSession
import db,config
import time,os
import xml.etree.ElementTree as ET
import sys,socket,time,re,datetime,threading
import sqlite3,logging
import db_service

logging.basicConfig(filename='service_log.txt', level=logging.ERROR)

class SilicanListener:

    def start(self):
        self.config = db_service.load_config()
        print(self.config)
        logins = self.config['login'].split(",")
        password = self.config['password']
        for login in logins:
            silican_starter = threading.Thread(target=self.silican_listener, args=(login,password))
            silican_starter.start()
            time.sleep(1)
    
    def connect(self):
        self.config = db_service.load_config()
        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock.settimeout(10)
            self.sock.connect((self.config['silican_address'],self.config['silican_port']))
            self.sock.settimeout(None)
        except Exception as e:
            print(str(e))
            logging.error("connect() : ", exc_info=True)

    def sendall(self,message):
        try:
            self.sock.sendall(message)
        except Exception as e:
            logging.error("sendall() : ", exc_info=True)

    def login(self,login,password):
        message = '<XCTIP><Log><MakeLog><CId>12</CId><Login>%s</Login><Pass>%s</Pass></MakeLog></Log></XCTIP>' % (login,password)
        self.sendall(message.encode('UTF-8'))

    def register_req(self):
        message = b'<XCTIP><Calls><Register_REQ><CId>1</CId></Register_REQ></Calls></XCTIP>'
        self.sendall(message)

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

    def resock(self):
        self.sock.shutdown(socket.SHUT_RDWR)
        self.sock.close()
        self.connect()
        self.sock.settimeout(60)
        self.login()
        self.register_req()

    def silican_listener(self,login,password):
        print("STARTED:",login)
        self.parser = ET.XMLPullParser(['end'])
        self.connect()
        self.sock.settimeout(60)
        self.login(login,password)
        self.register_req()

        self._login = login
        self.running = True

        while self.running:
            try:
                elem = self.read_frame()
                self.parse_element(elem)
            except socket.timeout as e:
                print("Registering for Change_EV ......")
                self.register_req()
            except socket.error as e:
                logging.error("SilicanConnectionThread() : ", exc_info=True)
                print("socket.error exception: ","SilicanConnectionThread: "+str(e))
                self.resock()
            except Exception as e:
                logging.error("SilicanConnectionThread() : ", exc_info=True)
                print("SilicanConnectionThread exception: ","SilicanConnectionThread: "+str(e))
                self.resock()

    def parse_element(self,elem):
        change = elem.findall(".//Change_EV")

        for row in change:
            calls_state = row.find(".//CallsState").text
            cr = row.find(".//CR").text

            calling = "Nie wykryto numeru"
            if row.find(".//Calling/Number") is not None:
                calling = row.find(".//Calling/Number").text
                if calling == "0":
                    calling = "Nie wykryto numeru"

            called = 0
            if row.find(".//Called/Number") is not None:
                called = row.find(".//Called/Number").text

            rel_cause = ''
            if row.find(".//RelCause") is not None:
                rel_cause = row.find(".//RelCause").text
                    
            if calls_state == "NewCall_ST":
                unix_time = int(time.time())
                sql = "INSERT INTO current_calls (cr,start_time,calls_state,calling_number,called_number,login,start_time_unix) VALUES ('%s','%s','%s','%s','%s','%s','%s')"  % (cr,datetime.now().strftime("%m-%d-%Y, %H:%M:%S"),calls_state,calling,called,'-',unix_time)

                print(sql)
                db_service.execute(sql)

            if calls_state == "Connect_ST":
                sql = "UPDATE current_calls SET calls_state = '%s', login = '%s'  WHERE cr = '%s'" % (calls_state,self._login,cr)

                print(sql)
                db_service.execute(sql)

            #if calls_state == "Release_ST":
            #    self._signal.emit((config.SILICAN_RELEASE,''))
            #    if rel_cause:
            #        sql = "UPDATE current_calls SET calls_state = '%s' WHERE cr = '%s'" % (rel_cause,cr)
            #        self._signal.emit((config.SILICAN_SQL,sql))

            
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

    #listener = SipListener()
    #listener.start()

    silican = SilicanListener()
    silican.start()
