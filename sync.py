#!/usr/bin/env python3

import sys,socket,time
from PyQt5.QtCore import QThread, pyqtSignal,Qt
from conf import silican_address,silican_credentials,local_db
import sqlite3

#XML
import xml.etree.ElementTree as ET

class DoneParsing(Exception):
    pass

class CallHistoryThread(QThread):
    _signal = pyqtSignal(int)
    _db_signal = pyqtSignal(int)
    def __init__(self):
        super(CallHistoryThread, self).__init__()
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.connect(silican_address)
        self.sock.settimeout(5)
        self.init_db()

        #<Row>
        #<Marker>CH000001F70000000A615ADCD703E986</Marker>
        #<RowType>AddRow</RowType>
        #<SyncType>HistoryCall</SyncType>
        #<HistoryCall>
        #  <HId>10</HId>
        #  <StartTime>2021-10-04 13:23:14</StartTime>
        #  <HType>MissedCall</HType>
        #  <DialNumber>615555555</DialNumber>
        #  <DurationTime>25</DurationTime>
        #  <Attempts>1</Attempts>
        #</HistoryCall>
      #</Row>

    def init_db(self):
        conn = sqlite3.connect(local_db)
        c = conn.cursor()
        #c.execute('DROP TABLE history_calls')
        c.execute('CREATE TABLE IF NOT EXISTS history_calls (marker varchar(255) PRIMARY KEY, row_type var_char(32), sync_type varchar(255), hid INTEGER, start_time TEXT, h_type  varchar(256), dial_number INTEGER, duration_time INTEGER, attempts INTEGER)')        
        conn.commit()

        c.execute('SELECT marker,start_time FROM history_calls ORDER BY hid DESC')
        try:
            last = c.fetchone()
            self.last_marker = last[0]
        except Exception:
            self.last_marker = ''

        self.last_marker = ''

    def __del__(self):
        self.wait()

    def read_frame(self):
        self.parser.feed("<root>")

        while True:
            data = self.sock.recv(1)
            data = data.decode("utf-8")
            self.parser.feed(data)
            for event, elem in self.parser.read_events():
                if elem.tag == 'XCTIP':
                    #print("READ FRAME",elem)
                    ET.dump(elem)
                    return elem

    def login(self):
        message = '<XCTIP><Log><MakeLog><CId>12</CId><Login>%s</Login><Pass>%s</Pass></MakeLog></Log></XCTIP>' % silican_credentials
        self.sock.sendall(message.encode('UTF-8'))
        
    def request_marker(self,marker,frames):
        message = '<XCTIP><Sync><Sync_REQ><CId>9</CId><Marker>%s</Marker><SyncType>HistoryCall</SyncType><Limit>%s</Limit></Sync_REQ></Sync></XCTIP>' % (marker,frames)
        self.sock.sendall(message.encode('UTF-8'))

    def run(self):
        self.parser = ET.XMLPullParser(['end'])
        conn = sqlite3.connect(local_db)
        c = conn.cursor()

        self.login()
        frames = 2
        self.request_marker(self.last_marker,frames)

        while True:
            try:
                elem = self.read_frame()
                error = elem.findall(".//Error")
                if error:
                    print(error)
                    return
                for row in elem.findall(".//Row"):
                    marker = row.find('Marker').text
                    row_type = row.find('RowType').text
                    sync_type = row.find('SyncType').text
                    history_call = row.find('HistoryCall')

                    if row_type == "RowEnd":
                        self._db_signal.emit(1)
                        print("ROWEND")
                        raise Exception('ROWEND')

                    if row_type == 'AddRow':
                        if history_call is not None:
                            start_time = history_call.find('StartTime').text
                            h_id = history_call.find('HId').text

                            h_type = history_call.find('HType').text
                            duration_time = history_call.find('DurationTime').text
                                    
                            dial_number = 0
                            if history_call.find('DialNumber') is not None:
                                dial_number = history_call.find('DialNumber').text
                                
                            attempts = 0
                            if history_call.find('Attempts') is not None:
                                attempts = history_call.find('Attempts').text

                            data = (marker,row_type,sync_type,h_id,start_time,h_type,dial_number,duration_time,attempts)
                            try:
                                c.execute("INSERT INTO history_calls VALUES (?,?,?,?,?,?,?,?,?)", data)
                                conn.commit()
                                print(data)
                            except sqlite3.IntegrityError as e:
                                print(str(e))

                    self.last_marker = marker
                    self.request_marker(marker,1)

            except socket.timeout as t:
                print(self.last_marker)
                self.request_marker(self.last_marker,2)
                
            except Exception as e:
                #raise
                print(str(e))
            
        time.sleep(0.1)
        self._signal.emit(50)
