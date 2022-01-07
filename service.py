from sip import SIPSession
import db,config
import time,os
import xml.etree.ElementTree as ET
import sys,socket,time,re,datetime,threading
import sqlite3,logging
import db_service

logging.basicConfig(filename='service_log.txt', level=logging.ERROR)

class SilicanListener:

    def start(self,login,password,config):
        self.cursor = db_service.init_db()
        self.config = config
        silican_starter = threading.Thread(target=self.silican_listener, args=(login,password))
        silican_starter.start()
    
    def connect(self):
        self.config = db_service.load_config(self.cursor)
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

    def resock(self,login,password):
        self.sock.shutdown(socket.SHUT_RDWR)
        self.sock.close()
        self.connect()
        self.sock.settimeout(60)
        self.login(login,password)
        self.register_req()

    def silican_listener(self,login,password):
        print("Silican thread started for login: :",login)
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
                self.resock(login,password)
            except Exception as e:
                logging.error("SilicanConnectionThread() : ", exc_info=True)
                print("SilicanConnectionThread exception: ","SilicanConnectionThread: "+str(e))
                self.resock(login,password)

    def parse_element(self,elem):
        change = elem.findall(".//Change_EV")

        for row in change:
            calls_state = row.find(".//CallsState").text
            cr = row.find(".//CR").text

            #<Colp>
            #<Number>212</Number>
            #<Comment>Abonent 212 Szymon</Comment>
            #</Colp>
            colp = ""
            if row.find(".//Colp/Number") is not None:
                colp = row.find(".//Colp/Number").text

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
                #sql = "INSERT INTO current_calls (cr,start_time,calls_state,calling_number,called_number,login,start_time_unix,colp,attempts) VALUES ('%s','%s','%s','%s','%s','%s','%s','%s','%s')"  % (cr,datetime.datetime.now().strftime("%m-%d-%Y, %H:%M:%S"),calls_state,calling,called,'-',unix_time,colp,1)

                #try:
                calling = calling.lstrip('0')
                sql = "UPDATE voip_calls SET call_received='%s' WHERE call_id=(SELECT TOP 1 call_id FROM voip_calls WHERE calling_number='%s' ORDER BY start_time_unix DESC)" % (self._login,calling)

                #print(sql)
                #db_service.execute(self.cursor,sql)
#except:
 #                   sql = "UPDATE current_calls SET calls_state='%s',colp='%s',start_time='%s',start_time_unix='%s',attempts=attempts+1 WHERE cr='%s'" % (calls_state,colp,datetime.datetime.now().strftime("%m-%d-%Y, %H:%M:%S"),unix_time,cr)
 #                   print(sql)
#                    db_service.execute(self.cursor,sql)

#<Change_EV>
#      <Src_Id>1008</Src_Id>
#      <Dst_Id>1008</Dst_Id>
#      <CallsState>Connect_ST</CallsState>
#      <CR>4118</CR>
#      <Calling>
#        <TerminalType>SuboIP</TerminalType>
#        <Number>2160</Number>
#        <Comment>Abonent 2160</Comment>
#        <Group>Subiekt</Group>
#      </Calling>
#      External number
#      <Calling>
#        <Number>0784021970</Number>
#        <AreaCode>GSM</AreaCode>
#      </Calling>
#      <Colp>
#        <Number>208</Number>
#        <Comment>Abonent 208 Pawel</Comment>
#      </Colp>
#      <Called>
#        <Number>208</Number>
#        <Comment>Abonent 208 Pawel</Comment>
#      </Called>
#    </Change_EV>

            if calls_state == "Connect_ST":
                calling = calling.lstrip('0')
                sql = "UPDATE voip_calls SET call_received='%s' WHERE call_id=(SELECT TOP 1 call_id FROM voip_calls WHERE calling_number='%s' ORDER BY start_time_unix DESC)" % (self._login,calling)
                print(sql)
                db_service.execute(self.cursor,sql)

class SipListener:
    def start(self):
        self.cursor = db_service.init_db()
        self.config = db_service.load_config(self.cursor)
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
            db_service.execute(self.cursor,sql)
                        
        except Exception as e:
            print(str(e))

if __name__ == "__main__":
    cursor = db_service.init_db()
    db_service.init_tables(cursor)

    listener = SipListener()
    listener.start()

    config = db_service.load_config(cursor)
    logins = config['login'].split(",")
    #logins = ['201','202']
    password = config['password']
    for login in logins:
        listener = SilicanListener()
        listener.start(login,password,config)
        time.sleep(1)
