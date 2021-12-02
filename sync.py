#!/usr/bin/env python3

import sys,socket,time
from PyQt5.QtCore import QThread, pyqtSignal,Qt
from conf import silican_credentials,local_db
import sqlite3,logging
from xml.dom import minidom

logging.basicConfig(filename='mikran.log', level=logging.DEBUG)

from datetime import datetime

#XML
import xml.etree.ElementTree as ET

class RowEndException(Exception):
    pass

class CallHistoryThread(QThread):
    _signal = pyqtSignal(int)
    _db_signal = pyqtSignal(tuple)
    def __init__(self):
        super(CallHistoryThread, self).__init__()
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        conn = sqlite3.connect(local_db)
        c = conn.cursor()
        c.execute('SELECT silican_address,silican_port FROM config')
        try:
            silican_address = c.fetchone()
        except Exception:
            pass
        
        self.sock.connect(silican_address)
        self.sock.settimeout(30)
        self.init_db()

        """
        <Row>
        <Marker>CE000002CF00000C4F615ADCD703E960</Marker>
        <RowType>AddRow</RowType>
        <SyncType>HistoryCall</SyncType>
        <HistoryCall>
          <HId>3151</HId>
          <StartTime>2021-11-06 11:40:26</StartTime>
          <HType>MissedCall</HType>
          <CNumber>0601570947</CNumber>
          <CName>Tomasz Zdanowski Mikran</CName>
          <CType>National</CType>
          <DialNumber>613067271</DialNumber>
          <DurationTime>9</DurationTime>
          <Unread>1</Unread>
          <Attempts>1</Attempts>
        </HistoryCall>
        </Row>
        """

    def init_db(self):
        conn = sqlite3.connect(local_db)
        c = conn.cursor()
        #c.execute('DROP TABLE history_calls')
        c.execute('CREATE TABLE IF NOT EXISTS history_calls (marker varchar(255), row_type var_char(32), sync_type varchar(255), hid INTEGER PRIMARY KEY, start_time TEXT, h_type  varchar(256), dial_number INTEGER, duration_time INTEGER, attempts INTEGER, cnumber varchar(255), cname varchar(255))')        
        conn.commit()

        #c.execute('SELECT marker,start_time FROM history_calls ORDER BY hid DESC')
        #try:
        #    last = c.fetchone()
        #    self.last_marker = last[0]
        #except Exception:
        #    self.last_marker = ''

        self.last_marker = ''
            
    def __del__(self):
        self.wait()

    def read_frame(self):
        self.parser.feed("<root>")

        while True:
            try:
                data = self.sock.recv(1)
                data = data.decode("utf-8")
                self.parser.feed(data)
                for event, elem in self.parser.read_events():
                    if elem.tag == 'XCTIP':
                        #print("READ FRAME:")
                        ET.dump(elem)
                        return elem
            except ET.ParseError as e:
                pass
            except socket.timeout:
                self.register_history_request()
                print(datetime.now())
                print("HISTORY REQ")
                pass

    def login(self):
        message = '<XCTIP><Log><MakeLog><CId>12</CId><Login>%s</Login><Pass>%s</Pass></MakeLog></Log></XCTIP>' % silican_credentials
        self.sock.sendall(message.encode('UTF-8'))
        
    def request_marker(self,marker,frames=1):
        message = '<XCTIP><Sync><Sync_REQ><CId>9</CId><Marker>%s</Marker><SyncType>HistoryCall</SyncType><Limit>%s</Limit></Sync_REQ></Sync></XCTIP>' % (marker,frames)
        self.sock.sendall(message.encode('UTF-8'))

    def request_book_marker(self,marker,frames=1):
        message = '<XCTIP><Sync><Sync_REQ><CId>9</CId><Marker>%s</Marker><SyncType>Book</SyncType><Limit>%s</Limit></Sync_REQ></Sync></XCTIP>' % (marker,frames)
        self.sock.sendall(message.encode('UTF-8'))

    def register_history_request(self):
        message = "<XCTIP><Sync><Register_REQ><CId>4</CId><SyncType>HistoryCall</SyncType></Register_REQ></Sync></XCTIP>"
        self.sock.sendall(message.encode('UTF-8'))

    def run(self):
        self.parser = ET.XMLPullParser(['end'])
        conn = sqlite3.connect(local_db)
        c = conn.cursor()

        self.login()
        self.register_history_request()
        self.request_marker(self.last_marker,2)
        #self.request_book_marker(self.last_marker,2)
        
        while True:
            try:
                elem = self.read_frame()
                error = elem.findall(".//Error")
                if error:
                    #ET.dump(error)
                    return

                change = elem.findall(".//Change_EV")
                if change:
                    #self.register_history_request()
                    self.request_marker(self.last_marker,2)
                
                for row in elem.findall(".//Row"):
                    marker = row.find('Marker').text
                    row_type = row.find('RowType').text
                    sync_type = row.find('SyncType').text
                    history_call = row.find('HistoryCall')

                    if row_type == "RowEnd":
                        self._db_signal.emit(())
                        self.last_marker = marker
                        raise RowEndException('ROWEND at marker: ',marker)

                    if row_type == 'Update':
                        if history_call is not None:
                            start_time = history_call.find('StartTime').text
                            h_id = history_call.find('HId').text

                            attempts = 0
                            if history_call.find('Attempts') is not None:
                                attempts = history_call.find('Attempts').text

                            data = (start_time,attempts,h_id)
                            try:
                                c.execute("UPDATE history_calls SET start_time = ?, attempts = ? WHERE hid = ?", data)
                                conn.commit()
                            except:
                                raise

                            self._db_signal.emit(data)

                    if row_type == 'AddRow':
                        if history_call is not None:
                            start_time = history_call.find('StartTime').text
                            h_id = history_call.find('HId').text

                            h_type = history_call.find('HType').text
                            duration_time = history_call.find('DurationTime').text
                                    
                            dial_number = 0
                            if history_call.find('DialNumber') is not None:
                                dial_number = history_call.find('DialNumber').text

                            cnumber = 0
                            if history_call.find('CNumber') is not None:
                                cnumber = history_call.find('CNumber').text

                            cname = ''
                            if history_call.find('CName') is not None:
                                cname = history_call.find('CName').text
          
                            attempts = 0
                            if history_call.find('Attempts') is not None:
                                attempts = history_call.find('Attempts').text

                            data = (marker,row_type,sync_type,h_id,start_time,h_type,dial_number,duration_time,attempts,cnumber,cname)
                            
                            try:
                                c.execute("INSERT INTO history_calls VALUES (?,?,?,?,?,?,?,?,?,?,?)", data)
                                conn.commit()
                            except sqlite3.IntegrityError as e:
                                data = (start_time,attempts,h_id)
                                c.execute("UPDATE history_calls SET start_time = ?, attempts = ? WHERE hid = ?", data)
                                conn.commit()
                            #except sqlite3.OperationalError as oe:
                            #    conn.close()
                            #    conn = sqlite3.connect(local_db)
                            #    c = conn.cursor()

                        self.request_marker(marker)

            except RowEndException:
                self._signal.emit((0,"marker"))
                pass        
