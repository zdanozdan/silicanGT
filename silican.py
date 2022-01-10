from PyQt5.QtCore import QThread, pyqtSignal,Qt
import db,config
import time,os
import xml.etree.ElementTree as ET
import sys,socket,time
from datetime import datetime
import sqlite3,logging

logging.basicConfig(filename='logfile.txt', level=logging.ERROR)

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

    def sendall(self,message):
        try:
            self.sock.sendall(message)
        except Exception as e:
            self._signal.emit((config.SILICAN_ERROR,"SendAll: "+str(e)))
            logging.error("connect() : ", exc_info=True)

    def login(self):
        message = '<XCTIP><Log><MakeLog><CId>12</CId><Login>%s</Login><Pass>%s</Pass></MakeLog></Log></XCTIP>' % (self.config['login'],self.config['password'])
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
            except UnicodeError as e:
                #self._signal.emit((config.SILICAN_ERROR,"read_frame: "+str(e)))
                pass

class SilicanConnectionThread(SilicanThreadBase):
    def stop(self):
        self.sock.shutdown(socket.SHUT_RDWR)
        self.sock.close()
        self.running = False

    def resock(self):
        self.sock.shutdown(socket.SHUT_RDWR)
        self.sock.close()
        self.connect()
        self.sock.settimeout(60)
        self.login()
        self.register_req()
        
    def run(self):
        self.parser = ET.XMLPullParser(['end'])
        self.connect()
        self.sock.settimeout(60)
        self.login()
        self.register_req()
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
                #self._signal.emit((config.SILICAN_ERROR,"SilicanConnectionThread: "+str(e)))

        #self._signal.emit((config.SILICAN_ERROR,"Program zakończył działanie ..."))
        print("SilicanConnectionThread FINISHED")

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
                self._signal.emit((config.SILICAN_CONNECTION,calling))
                user = db.find_user(str(calling))
                if user:
                    self._signal.emit((config.SILICAN_USER_FOUND,user))
                    calling = user['tel_Numer']

                unix_time = int(time.time())
                sql = "INSERT INTO current_calls (cr,start_time,calls_state,calling_number,called_number,login,start_time_unix) VALUES ('%s','%s','%s','%s','%s','%s','%s')"  % (cr,datetime.now().strftime("%m-%d-%Y, %H:%M:%S"),calls_state,calling,called,self.config['login'],unix_time)
                self._signal.emit((config.SILICAN_SQL,sql))

            if calls_state == "Connect_ST":
                sql = "UPDATE current_calls SET calls_state = '%s' WHERE cr = '%s'" % (calls_state,cr)
                self._signal.emit((config.SILICAN_SQL,sql))

            if calls_state == "Release_ST":
                self._signal.emit((config.SILICAN_RELEASE,''))
                if rel_cause:
                    sql = "UPDATE current_calls SET calls_state = '%s' WHERE cr = '%s'" % (rel_cause,cr)
                    self._signal.emit((config.SILICAN_SQL,sql))

class SilicanHistoryThread(SilicanThreadBase):

    def request_marker(self,marker,frames=1):
        message = '<XCTIP><Sync><Sync_REQ><CId>9</CId><Marker>%s</Marker><SyncType>HistoryCall</SyncType><Limit>%s</Limit></Sync_REQ></Sync></XCTIP>' % (marker,frames)
        self.sendall(message.encode('UTF-8'))

    def register_history_request(self):
        message = "<XCTIP><Sync><Register_REQ><CId>4</CId><SyncType>HistoryCall</SyncType></Register_REQ></Sync></XCTIP>"
        self.sendall(message.encode('UTF-8'))

    def loop(self,elem):
        error = elem.findall(".//Error")
        if error:
            #ET.dump(error)
            self._signal.emit((config.SILICAN_ERROR,str(error)))
            return False

        change = elem.findall(".//Change_EV")
        if change:
            self.request_marker(self.last_marker,2)
            return True
                
        for row in elem.findall(".//Row"):
            marker = row.find('Marker').text
            row_type = row.find('RowType').text
            sync_type = row.find('SyncType').text
            history_call = row.find('HistoryCall')
            
            if row_type == "RowEnd":
                self.last_marker = marker
                return False

            if row_type == 'DelAll':
                self._signal.emit((config.SILICAN_ERROR,"Usuń historię"))

            if row_type == 'Update':
                if history_call is not None:
                    start_time = history_call.find('StartTime').text
                    h_id = history_call.find('HId').text

                    attempts = 0
                    if history_call.find('Attempts') is not None:
                        attempts = history_call.find('Attempts').text

                    data = (start_time,attempts,h_id)
                    sql = "UPDATE history_calls SET start_time = '%s', attempts = '%s' WHERE hid = '%s'" % data
                    self._signal.emit((config.SILICAN_HISTORY_SQL,sql))
                    print("UPDATE:",sql)

            if row_type == 'AddRow':
                if history_call is not None:
                    start_time = history_call.find('StartTime').text
                    h_id = history_call.find('HId').text
                        
                    h_type = history_call.find('HType').text
                    duration_time = history_call.find('DurationTime').text
                                    
                    dial_number = 0
                    if history_call.find('DialNumber') is not None:
                        dial_number = history_call.find('DialNumber').text

                    calling = 0
                    if history_call.find('CNumber') is not None:
                        calling = history_call.find('CNumber').text

                    cname = ''
                    if history_call.find('CName') is not None:
                        cname = history_call.find('CName').text
          
                    attempts = 0
                    if history_call.find('Attempts') is not None:
                        attempts = history_call.find('Attempts').text

                    user = db.find_user(str(calling))
                    if user:
                        calling_number = user['tel_Numer']
                    else:
                        calling_number = calling
                        
                    data = (marker,row_type,sync_type,h_id,start_time,h_type,dial_number,duration_time,attempts,calling_number,cname,self.config['login'])
                    sql = "INSERT INTO history_calls (marker,row_type,sync_type,hid,start_time,h_type,dial_number,duration_time,attempts,calling_number,cname,login) VALUES ('%s','%s','%s','%s','%s','%s','%s','%s','%s','%s','%s','%s')" % data
                    self._signal.emit((config.SILICAN_HISTORY_SQL,sql))
                    self.request_marker(marker)

        return True
        
    def run(self):
        self.parser = ET.XMLPullParser(['end'])
        self.connect()
        self.sock.settimeout(None)
        self.login()

        try:
            self.last_marker = db.get_last_marker()
            self.request_marker(self.last_marker,1)
        except:
            self.last_marker = ''
            self.request_marker(self.last_marker,2)

        self.running = True
        while self.running:
            try:
                elem = self.read_frame()
                self.running = self.loop(elem)
            except socket.timeout as e:
                pass
            except Exception as e:
                self._signal.emit((config.SILICAN_ERROR,"SilicanHistoryThread: "+str(e)))
                logging.error("SilicanConnectionThread() : ", exc_info=True)
        
        self._signal.emit((config.SILICAN_SUCCESS,"Zakończone pobieranie historii"))
                        

class SilicanHistoryEventsThread(SilicanHistoryThread):
    def stop(self):
        self.sock.shutdown(socket.SHUT_RDWR)
        self.sock.close()
        self.running = False

    def resock(self):
        self.sock.shutdown(socket.SHUT_RDWR)
        self.sock.close()
        self.connect()
        self.sock.settimeout(60)
        self.login()
        self.register_history_request()
        
    def run(self):
        self.last_marker = ''
        try:
            self.last_marker = db.get_last_marker()
        except:
            pass
        
        self.parser = ET.XMLPullParser(['end'])
        self.connect()
        self.sock.settimeout(60)
        self.login()
        self.register_history_request()
        self.running = True
        
        while self.running:
            try:
                elem = self.read_frame()
                run = self.loop(elem)
            except socket.timeout as e:
                pass
                #print("Re-register for events")
                #self.register_history_request()
            except socket.error as e:
                logging.error("SilicanHistoryThread() : ", exc_info=True)
                print("socket.error exception: ","SilicanHistoryEventsThread :"+str(e))             
                self.resock()
            except Exception as e:
                print("SilicanHistoryEventsThread exception",str(e))
                logging.error("SilicanHistoryThread() : ", exc_info=True)
                self.resock()
                self._signal.emit((config.SILICAN_ERROR,"SilicanHistoryEventsThread: "+str(e)))

        print("SilicanHistoryEventsThread FINISHED")
