from PyQt5.QtCore import QThread, pyqtSignal,Qt
import db,config
import time,os
import xml.etree.ElementTree as ET
import sys,socket,time
from datetime import datetime
import sqlite3

class SilicanThreadBase(QThread):
    _signal = pyqtSignal(tuple)
    
    def __init__(self,parent=None):
        super(SilicanThreadBase, self).__init__(parent=parent)
        
    #def __del__(self):
    #    self.wait()

    def connect(self):
        self.config = db.load_config()
        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock.settimeout(10)
            self.sock.connect((self.config['silican_address'],self.config['silican_port']))
            self.sock.settimeout(None)
            self._signal.emit((config.SILICAN_CONNECTED,"OK"))
        except socket.timeout as e:
            self._signal.emit((config.SILICAN_ERROR,str(e)))
        except socket.error as e:
            self._signal.emit((config.SILICAN_ERROR,str(e)))
            #raise

    def login(self):
        message = '<XCTIP><Log><MakeLog><CId>12</CId><Login>%s</Login><Pass>%s</Pass></MakeLog></Log></XCTIP>' % (self.config['login'],self.config['password'])
        self.sock.sendall(message.encode('UTF-8'))

    def register_req(self):
        #message = b'<XCTIP><Calls><Register_REQ><CId>1</CId><Id>1001</Id><Pass>mikran123</Pass></Register_REQ></Calls></XCTIP>'
        message = b'<XCTIP><Calls><Register_REQ><CId>1</CId></Register_REQ></Calls></XCTIP>'
        self.sock.sendall(message)

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
            except socket.timeout as e:
                print("Registering for Change_EV ......")
                self.register_req()
            except Exception as e:
                print(str(e))
            

class SilicanConnectionThread(SilicanThreadBase):
    def stop(self):
        print("stopped")
        self.sock.close()
        os._exit(0)
        
    def run(self):
        self.parser = ET.XMLPullParser(['end'])
        self.connect()
        self.sock.settimeout(60)
        self.login()
        self.register_req()

        while True:
            elem = self.read_frame()
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

                if calls_state == "NewCall_ST":
                    self._signal.emit((config.SILICAN_CONNECTION,calling))
                    user = db.find_user(str(calling))
                    if user:
                        self._signal.emit((config.SILICAN_USER_FOUND,user))
                        calling = user['tel_Numer']


                    sql = "INSERT INTO current_calls (cr,start_time,calls_state,calling_number,called_number) VALUES ('%s','%s','%s','%s','%s')"  % (cr,datetime.now().strftime("%m-%d-%Y, %H:%M:%S"),calls_state,calling,called)
                    self._signal.emit((config.SILICAN_SQL,sql))
                    #try:
                    #    c.execute("INSERT INTO current_calls (cr,start_time,calls_state,calling_number,called_number) VALUES ('%s','%s','%s','%s','%s')"  % (cr,datetime.now().strftime("%m-%d-%Y, %H:%M:%S"),calls_state,calling,called))
                    #    conn.commit()
                    #except sqlite3.IntegrityError as e:
                        #data = (calls_state,datetime.now().strftime("%m-%d-%Y, %H:%M:%S"),cr)
                        #c.execute("UPDATE current_calls SET calls_state = ?, start_time = ? WHERE cr = ?", data)
                        #conn.commit()
                    #    raise

                if calls_state == "Release_ST":
                    self._signal.emit((config.SILICAN_RELEASE,''))
