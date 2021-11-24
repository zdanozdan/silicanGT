#!/usr/bin/env python3

import sys,socket,time
from PyQt5 import QtCore
from PyQt5.QtCore import QThread, pyqtSignal,Qt
from PyQt5.QtWidgets import QWidget, QTabWidget, QPushButton, QProgressBar, QVBoxLayout, QFormLayout, QLineEdit, QApplication,QStatusBar,QMainWindow,QLabel,QMenuBar,QMenu,QAction,QToolBar,QToolButton,QTableView,QMessageBox,QDialog
from PyQt5 import QtWidgets
from PyQt5 import QtGui
from PyQt5.QtGui import QIcon
from PyQt5.QtSql import QSqlDatabase, QSqlTableModel, QSqlQuery

#XML
import xml.etree.ElementTree as ET
#Thread
from sync import CallHistoryThread
#sqlite
import sqlite3
from datetime import datetime

from conf import local_db

FRAME_SUCCESS = 0
FRAME_EXCEPTION = 1

class Window(QMainWindow):
    def __init__(self, parent=None):
        """Initializer."""
        super().__init__(parent)
        self.setWindowTitle("mikran.pl - integracja centrali telefonicznej")
        self.resize(800, 600)
        self.centralWidget = CentralWidget()
        self.createMenuBar()
        self.createToolBar()
        self.statusBar().showMessage('Message in statusbar.')
        
        self.setCentralWidget(self.centralWidget)

        self.con = QSqlDatabase.addDatabase("QSQLITE",'db1')
        self.con.setDatabaseName("silican.sqlite")
        if not self.con.open():
            QMessageBox.critical(
                None,
                "Database silican.sqlite error!",
                "Database Error: %s" % con.lastError().databaseText(),
            )

        query = QSqlQuery()
        query.exec(
            """
            CREATE TABLE IF NOT EXISTS config (silican_address var_char(255), silican_port INTEGER, login varchar(255), password varchar(255))
            """)

        query.exec("SELECT * FROM config")
        if query.first() == False:
            model = QSqlTableModel(self)
            model.setTable("config")
            record = model.record()
            record.setValue('silican_address', '192.168.0.2')
            record.setValue('silican_port', '5529')
            record.setValue('login', '201')
            record.setValue('password', 'mikran123')
            model.insertRecord(0, record)
            query.exec("SELECT * FROM config")
            query.first()

        index = query.record().indexOf('silican_address')
        self.silican_address = query.value(index)

        index = query.record().indexOf('silican_port')
        self.silican_port = query.value(index)

        index = query.record().indexOf('login')
        self.login = query.value(index)

        index = query.record().indexOf('password')
        self.password = query.value(index)

        #xml_string = "<XCTIP><Calls><Change_EV><Src_Id>1001</Src_Id><Dst_Id>1001</Dst_Id><CallsState>NewCall_ST</CallsState><CR>15822</CR><Calling><Number>123123123</Number></Calling><Colp><Number>201</Number><Comment>Abonent 201</Comment></Colp><Called><Number>615555555</Number></Called></Change_EV></Calls></XCTIP>"

        #query.exec(
        #    """
        #    DELETE FROM current_calls
        #    """
        #    )
            
        query.exec(
            """
            CREATE TABLE IF NOT EXISTS current_calls ( cr INTEGER PRIMARY KEY, start_time TEXT, calls_state var_char(255), calling_number varchar(255), called_number varchar(255))
            """)

        #model = QSqlTableModel(self)
        #model.setTable("current_calls")
        #record = model.record()
        #record.setValue('cr', '1')
        #record.setValue('calls_state', 'new')
        #record.setValue('calling_number', '123123123')
        #record.setValue('called_number', '123123123')
        #model.insertRecord(0, record)

        self.con.close()
        del self.con

    def connect(self):
        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock.settimeout(3)
            self.sock.connect((self.silican_address,self.silican_port))
            self.sock.settimeout(None)
            print((self.silican_address,self.silican_port))
            self.statusBar().setStyleSheet("color: green")
            self.statusBar().showMessage('Connected to silican on socket %s:%s' % (self.silican_address,self.silican_port))
        except socket.error as e:
            self.statusBar().setStyleSheet("color: red")
            self.statusBar().showMessage('Error %s' % str(e))

            QMessageBox.critical(
                None,
                "Socket Error, check silican configuration",
                "Connection Error: (%s)" % str(e),
            )
            raise

    def send_socket(self,msg):
        try:
            self.sock.sendall(msg)
        except Exception as e:
            self.statusBar().setStyleSheet("color: red")
            self.statusBar().showMessage(str(e))

    def start_workers(self):
        self.thread = CallHistoryThread()
        self.thread._db_signal.connect(self.centralWidget.signal_sync_db)
        self.thread.start()
    
        self.socketthread = SocketThread(self.sock)
        self.socketthread._signal.connect(self.signal_status)
        self.socketthread._db_signal.connect(self.centralWidget.signal_sync)        
        self.socketthread.start()

    def start(self):
        try:
            self.connect()
            self.startButton.setEnabled(False)
            message = '<XCTIP><Log><MakeLog><CId>12</CId><Login>%s</Login><Pass>%s</Pass></MakeLog></Log></XCTIP>' % (self.login,self.password)
            self.send_socket(message.encode('UTF-8'))
            self.start_workers()
            self.register_calls()
        except Exception as e:
            QMessageBox.critical(
                None,
                "Socket Error, check silican configuration",
                "Connection Error: (%s)" % str(e),
            )

    def register_calls(self):
        message = b'<XCTIP><Calls><Register_REQ><CId>1</CId><Id>1001</Id><Pass>mikran123</Pass></Register_REQ></Calls></XCTIP>'
        self.send_socket(message)

    def signal_status(self,msg):
        if msg[0] == FRAME_EXCEPTION:
            self.statusBar().setStyleSheet("color: red")
        else:
            self.statusBar().setStyleSheet("color: green")

        self.statusBar().showMessage(msg[1])
        
    def settings(self):
        self.settings_widget = QDialog()
        self.settings_widget.setModal(True)

        model = QSqlTableModel(self)
        model.setTable("config")  
        #self.model.setEditStrategy(QSqlTableModel.OnFieldChange)
        #model.setHeaderData(8, Qt.Horizontal, "Ilość prób")

        tableview = QTableView()
        tableview.setModel(model)
        tableview.setSortingEnabled(True)
        tableview.sortByColumn(0, Qt.DescendingOrder);

        vbox = QVBoxLayout()
        vbox.addWidget(tableview)
        self.settings_widget.setLayout(vbox)        
        self.settings_widget.show()

    def my_test(self):
        pass
    
    def ping(self):
        message = b'<XCTIP><Stream><WDTest></WDTest></Stream></XCTIP>'
        self.send_socket(message)

    def createToolBar(self):
        self.toolBar = QToolBar("My main toolbar")
        self.addToolBar(self.toolBar)

        self.startButton = QToolButton()
        self.startButton.setText("Start")
        self.startButton.clicked.connect(self.start)
        self.toolBar.addWidget(self.startButton)

        toolButton = QToolButton()
        toolButton.setText("Ping")
        toolButton.clicked.connect(self.ping)
        self.toolBar.addWidget(toolButton)

        toolButton = QToolButton()
        toolButton.setText("My Test")
        toolButton.clicked.connect(self.my_test)
        self.toolBar.addWidget(toolButton)

        toolButton = QToolButton()
        toolButton.setText("Settings")
        toolButton.clicked.connect(self.settings)
        self.toolBar.addWidget(toolButton)

    def createMenuBar(self):
        pass
        # Create new action
        #newAction = QAction(QIcon('new.png'), '&New', self)        
        #newAction.setShortcut('Ctrl+N')
        #newAction.setStatusTip('New document')
        #newAction.triggered.connect(self.newCall)
        
        #mainMenu = self.menuBar()
        #fileMenu = mainMenu.addMenu('&File')
        #fileMenu.addAction(newAction)

class SocketThread(QThread):
    _signal = pyqtSignal(tuple)
    _db_signal = pyqtSignal(tuple)
    def __init__(self,sock):
        super(SocketThread, self).__init__()
        self.sock = sock

        #def __del__(self):
        #self.wait()

    def read_frame(self):
        self.parser.feed("<root>")

        while True:
            try:
                data = self.sock.recv(1)
                data = data.decode("utf-8")
                self.parser.feed(data)
                for event, elem in self.parser.read_events():
                    if elem.tag == 'XCTIP':
                        print("READ FRAME",elem)
                        ET.dump(elem)
                        return elem
            except ET.ParseError as e:
                pass

#  <Calls>
#    <Change_EV>
#      <Src_Id>1001</Src_Id>
#      <Dst_Id>1001</Dst_Id>
#      <CallsState>Disconnect_ST</CallsState>
#      <CR>15822</CR>
#    </Change_EV>
#  </Calls>
#</XCTIP>
#<XCTIP>
#  <Calls>
#    <Change_EV>
#      <Src_Id>1001</Src_Id>
#      <Dst_Id>1001</Dst_Id>
#      <CallsState>Release_ST</CallsState>
#      <CR>15822</CR>
#    </Change_EV>
#  </Calls>
#</XCTIP>

    def run(self):
        self.parser = ET.XMLPullParser(['end'])
        conn = sqlite3.connect(local_db)
        c = conn.cursor()
        
        while True:
            try:
                elem = self.read_frame()
                ok = elem.findall(".//WDOk")
                if(ok):
                    self._signal.emit((FRAME_SUCCESS,"Ping OK"))
                errors = elem.findall(".//Error")
                for error in errors:                
                    self._signal.emit((FRAME_EXCEPTION, error.text))

                change = elem.findall(".//Change_EV")
                for row in change:
                    print(ET.dump(row))
                    calls_state = row.find(".//CallsState").text
                    cr = row.find(".//CR").text

                    calling = 0
                    if row.find(".//Calling/Number") is not None:
                        calling = row.find(".//Calling/Number").text

                    called = 0
                    if row.find(".//Called/Number") is not None:
                        called = row.find(".//Called/Number").text

                    data = (cr,calls_state,calling,called)
                    self._db_signal.emit(data)
                    #self._signal.emit(ET.tostring(row).encode('UTF-8'))
                    
                log = elem.findall(".//LogInfo_ANS")
                for row in log:
                    comment = row.find('Comment').text
                    self._signal.emit((FRAME_SUCCESS,comment))
                    
            except Exception as e:
                self._signal.emit((FRAME_EXCEPTION,str(e)))


class CentralWidget(QWidget):
    def __init__(self):
        super(CentralWidget, self).__init__()
        self.hid = 0
        self.label = QLabel("GT customer: #numer, #nazwa, #NIP")
        font = self.label.font()
        font.setPointSize(30)
        self.label.setFont(font)
        self.label.setAlignment(Qt.AlignHCenter | Qt.AlignVCenter)

        self.pbar = QProgressBar(self)
        self.pbar.setValue(0)

        con = QSqlDatabase.addDatabase("QSQLITE")
        con.setDatabaseName("silican.sqlite")
        if not con.open():
            QMessageBox.critical(
                None,
                "Database silican.sqlite error!",
                "Database Error: %s" % con.lastError().databaseText(),
            )

        self.model = CallsQSqlTableModel(self)
        self.setup_model(self.model,'history_calls')
        
        self.tableview = QTableView()
        self.tableview.setModel(self.model)
        self.setup_tableview()
        self.tableview.update()

        line_edit = QtWidgets.QLineEdit()
        line_edit.textChanged.connect(self.filter_number)

        self.all_checkbox = QtWidgets.QRadioButton("Wszystkie")
        self.all_checkbox.toggled.connect(lambda val: self.model.setFilter(""))
        self.all_checkbox.setChecked(True)
        
        self.missed_checkbox = QtWidgets.QRadioButton("Nieodebrane")
        self.missed_checkbox.toggled.connect(self.filter_missed)
        self.incoming_checkbox = QtWidgets.QRadioButton("Przychodzące")
        self.incoming_checkbox.toggled.connect(self.filter_incoming)
        self.outgoing_checkbox = QtWidgets.QRadioButton("Wychodzące")
        self.outgoing_checkbox.toggled.connect(self.filter_outgoing)
        self.latest_checkbox = QtWidgets.QRadioButton("Ostatnie")
        self.latest_checkbox.toggled.connect(self.filter_latest)

        self._filter,self._f = [],[]

        self.tabs = QTabWidget()
        self.tab1 = QWidget()
        self.tab2 = QWidget()
        self.tabs.addTab(self.tab1,"Bieżące połączenia")
        self.tabs.addTab(self.tab2,"Historyczne")

        self.current_model = CallsQSqlTableModel(self)
        #query = QSqlQuery("SELECT * FROM current_calls GROUP BY cr ORDER BY start_time DESC")
        #self.current_model.setQuery(query)
        self.current_model.setTable("current_calls")
        self.current_model.setHeaderData(0, Qt.Horizontal, "ID połączenia")
        self.current_model.setHeaderData(1, Qt.Horizontal, "Data i godzina")
        self.current_model.setHeaderData(2, Qt.Horizontal, "Typ")
        self.current_model.setHeaderData(3, Qt.Horizontal, "Numer")
        self.current_model.select()

        tableview_current = QTableView()
        tableview_current.setModel(self.current_model)
        tableview_current.sortByColumn(1, Qt.DescendingOrder);

        layout1 = QVBoxLayout()
        layout1.addWidget(tableview_current)
        self.tab1.setLayout(layout1)

        layout2 = QVBoxLayout()
        layout2.addWidget(self.tableview)
        self.tab2.setLayout(layout2)

        self.vbox = QVBoxLayout()
        self.vbox.addWidget(self.label)
        self.vbox.addWidget(line_edit)
        self.vbox.addWidget(self.all_checkbox)
        self.vbox.addWidget(self.missed_checkbox)
        self.vbox.addWidget(self.incoming_checkbox)
        self.vbox.addWidget(self.outgoing_checkbox)
        self.vbox.addWidget(self.latest_checkbox)
        self.vbox.addWidget(self.tabs)
        self.vbox.addWidget(self.pbar)

        self.setLayout(self.vbox)
        
        self.show()

    def signal_sync_db(self,_tuple):
        print("signal_sync_db. Update tableview: ", _tuple)
        #self.hid = hid
        #if hid > 0:
        #self.latest_checkbox.setChecked(True)

        #self.tableview.update()
        #('CH000000DD000000D9619779CD03E981', 'AddRow', 'HistoryCall', '217', '2021-11-22 13:41:34', 'InCall', '612222222', '290', 0, '0', '')
        #c.execute('CREATE TABLE IF NOT EXISTS history_calls (marker varchar(255), row_type var_char(32), sync_type varchar(255), hid INTEGER PRIMARY KEY, start_time
        #TEXT, h_type  varchar(256), dial_number INTEGER, duration_time INTEGER, attempts INTEGER, cnumber varchar(255), cname varchar(255))')        

        record = self.model.record()
        record.setValue('marker', _tuple[0])
        record.setValue('row_type', _tuple[1])
        record.setValue('sync_type', _tuple[2])
        record.setValue('hid', _tuple[3])
        record.setValue('start_time', _tuple[4])
        record.setValue('h_type', _tuple[5])
        record.setValue('dial_number', _tuple[6])
        record.setValue('duration_time', _tuple[7])
        record.setValue('attempts', _tuple[8])
        record.setValue('cnumber', _tuple[9])
        record.setValue('cname', _tuple[10])
        if not self.model.insertRecord(0, record):
            print("ERROR INSERT !!!!!")
            query = QSqlQuery("SELECT * FROM history_calls WHERE hid='%d'" % int(_tuple[3]))
            self.model.setQuery(query)
            if query.first() == True:
                record = self.model.record(0)
                record.setValue("attempts", 999)
                self.model.setRecord(0, record)
        #    QMessageBox.critical(
        #        None,
        #        "Database silican.sqlite error!",
        #        "Database Error: %s",
        #    )
        self.model.submitAll()

    def signal_sync(self,_tuple):
        print(_tuple)

        #query = QSqlQuery("SELECT * FROM current_calls WHERE cr='%d'" % int(_tuple[0]))
        #self.current_model.setQuery(query)
        #if query.first() == True:
        #    record = self.current_model.record(0)
        ##    record.setValue("calls_state", _tuple[1])
        #    record.setValue("start_time", datetime.now().strftime("%d-%m-%Y %H:%M:%S"))
        #    self.current_model.setRecord(0, record)
        #    self.current_model.submitAll()
        #else:
        record = self.current_model.record()
        record.setValue('cr', _tuple[0])
        record.setValue('calls_state', _tuple[1])
        record.setValue('calling_number', _tuple[2])
        record.setValue('called_number', _tuple[3])
        record.setValue('start_time', datetime.now().strftime("%d-%m-%Y %H:%M:%S"))
        self.current_model.insertRecord(0, record)
        self.current_model.submitAll()

    def setup_tableview(self):
        self.tableview.hideColumn(0)
        self.tableview.hideColumn(1)
        self.tableview.hideColumn(2)
        self.tableview.hideColumn(6)
        #self.tableview.resizeColumnsToContents()
        #self.tableview.horizontalHeader().setSectionResizeMode(QtWidgets.QHeaderView.Stretch)
        self.tableview.setSortingEnabled(True)
        self.tableview.sortByColumn(4, Qt.DescendingOrder);

    def setup_model(self,model,table):
        model.setTable(table)
        model.setHeaderData(3, Qt.Horizontal, "ID połączenia")
        model.setHeaderData(4, Qt.Horizontal, "Data i godzina")
        model.setHeaderData(5, Qt.Horizontal, "Typ")
        model.setHeaderData(6, Qt.Horizontal, "Numer")
        model.setHeaderData(7, Qt.Horizontal, "Długość połączenia (s)")
        model.setHeaderData(8, Qt.Horizontal, "Ilość prób")
        model.setHeaderData(9, Qt.Horizontal, "Numer")
        model.setHeaderData(10, Qt.Horizontal, "Abonent")
        model.select()

    def _build_filter(self,f,value):
        self._filter.append(f)        
        if not value:
            self._filter = list(filter((f).__ne__,self._filter))

        self.setFilter()

    def setFilter(self):
        sql = " AND ".join(self._f+self._filter)
        print("SQL: ",sql)
        self.model.setFilter(" AND ".join(self._f+self._filter))

    def filter_number(self,number):
        self._f = []
        if number:
            self._f = ["(cnumber like '%"+number+"%' OR cname like '%"+number+"%')",]

        self.setFilter()

    def filter_outgoing(self,value):
        _s = "h_type = 'OutCall'"
        self._build_filter(_s,value)

    def filter_latest(self,value):
        self.model.setFilter(" hid = '%d'" % self.hid)

    def filter_incoming(self,value):
        _s = "h_type = 'InCall'"
        self._build_filter(_s,value)

    def filter_missed(self,value):
        _s = "h_type = 'MissedCall'"
        self._build_filter(_s,value)
        
class CallsQSqlTableModel(QSqlTableModel):
   def __init__(self, dbcursor=None):
       super(CallsQSqlTableModel, self).__init__()
       self._color = QtCore.Qt.gray
 
   def data(self, QModelIndex, role=None):
       v = QSqlTableModel.data(self, QModelIndex, role);
       if role == QtCore.Qt.BackgroundRole:
           return QtGui.QColor(self._color)

       if role == Qt.DisplayRole or role == Qt.EditRole:
           self._color = '#f5f5dc'
           if v == 'MissedCall':
               self._color = QtCore.Qt.red
               return "Nieodebrane"
           if v == 'InCall':
               self._color = QtCore.Qt.green
               return "Przychodzące"
           if v == 'OutCall':
               self._color = '#ff8c00'
               return "Wychodzące"
               
       return v

if __name__ == "__main__":
    app = QApplication(sys.argv)
    ex = Window()
    ex.show()
    sys.exit(app.exec_())
