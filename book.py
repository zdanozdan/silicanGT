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

    def permission_req(self):
        message = b'<XCTIP><Sync><GetPermission_REQ><CId>12</CId><Id>1001</Id></GetPermission_REQ></Sync></XCTIP>';
        self.sendall(message)

    def sync_book_req(self,marker=''):
        #message = b'<XCTIP><Sync><Sync_REQ><CId>12</CId><Id>1001</Id><Marker>BG0000FDD0000000025FB3AD3203E97C</Marker><SyncType>Book</SyncType><Limit>1</Limit></Sync_REQ></Sync></XCTIP>'
        message = '<XCTIP><Sync><Sync_REQ><CId>12</CId><Id>1001</Id><Marker>%s</Marker><SyncType>Book</SyncType><Limit>1</Limit></Sync_REQ></Sync></XCTIP>' % marker
        self.sendall(message.encode('UTF-8'))

    def delete_book_req(self,contact_id = 20):
        message ='<XCTIP><Sync><SendChange_REQ><CId>1</CId><Id>1001</Id><Row><RowType>DelRow</RowType><Contact><ContactId>%s</ContactId></Contact></Row></SendChange_REQ></Sync></XCTIP>' % contact_id
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

    #def resock(self,login,password):
    #    self.sock.shutdown(socket.SHUT_RDWR)
    #    self.sock.close()
    #    self.connect()
    #    self.sock.settimeout(60)
    #    self.login(login,password)
    #    self.register_req()

    def silican_listener(self,login,password):
        print("Silican thread started for login: :",login)
        self.parser = ET.XMLPullParser(['end'])
        self.connect()
        self.sock.settimeout(60)
        self.login(login,password)
        #self.register_req()
        #self.permission_req()
        #self.sync_book_req()
        #self.delete_book_req()

        self._login = login
        self.running = True

        contact_id = 21
        while self.running:
            try:
                elem = self.read_frame()
                #self.parse_element(elem)
                self.delete_book_req(contact_id)
                contact_id = contact_id + 1
            #except socket.timeout as e:
            #    print("Registering for Change_EV ......")
            #    self.register_req()
            #except socket.error as e:
            #    logging.error("SilicanConnectionThread() : ", exc_info=True)
            #    print("socket.error exception: ","SilicanConnectionThread: "+str(e))
            #    self.resock(login,password)
            except Exception as e:
                logging.error("SilicanConnectionThread() : ", exc_info=True)
                print("SilicanConnectionThread exception: ","SilicanConnectionThread: "+str(e))
                #self.resock(login,password)

    def parse_element(self,elem):
        #<Contact>
        #<ContactId>20</ContactId>
        if elem.find(".//Contact/ContactId") is not None:
            contact_id = elem.find(".//Contact/ContactId").text
            print("CONTACT_ID",contact_id)

        if elem.find(".//Row/Marker") is not None:
            marker = elem.find(".//Row/Marker").text
            print("Marker: ",marker)
            self.sync_book_req(marker)
            time.sleep(2)
            

if __name__ == "__main__":
    cursor = db_service.init_db()
    db_service.init_tables(cursor)

    config = db_service.load_config(cursor)
    #logins = config['login'].split(",")
    logins = ['201',]
    password = config['password']
    for login in logins:
        listener = SilicanListener()
        listener.start(login,password,config)
        time.sleep(1)
