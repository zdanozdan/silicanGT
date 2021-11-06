#!/usr/bin/env python3

import sys,socket,time
from PyQt5 import QtCore
from PyQt5.QtCore import QThread, pyqtSignal,Qt
from PyQt5.QtWidgets import QWidget, QPushButton, QProgressBar, QVBoxLayout, QApplication,QStatusBar,QMainWindow,QLabel,QMenuBar,QMenu,QAction,QToolBar,QToolButton,QTableView,QMessageBox,QDialog
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
            record.setValue('silican_address', '192.168.0.22')
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

        self.con.close()
        del self.con

        #print(self.silican_address,self.silican_port,self.login,self.password)

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
        self.thread._signal.connect(self.signal_accept)
        self.thread._db_signal.connect(self.signal_sync_db)
        self.thread.start()
    
        self.socketthread = SocketThread(self.sock)
        self.socketthread._signal.connect(self.signal_status)        
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
        message = b'<?xml version="1.0" encoding="IBM852"?><XCTIP><Calls><Register_REQ><CId>1</CId><Id>1001</Id><Pass>mikran123</Pass></Register_REQ></Calls></XCTIP>'
        self.send_socket(message)

    def signal_sync_db(self,msg):
        print(msg,"signal_sync_db")
        query = QSqlQuery("select * from history_calls order by start_time desc")
        self.centralWidget.model.setQuery(query)
        self.centralWidget.setFilter()

    def signal_status(self,msg):
        if msg[0] == FRAME_EXCEPTION:
            self.statusBar().setStyleSheet("color: red")
        else:
            self.statusBar().setStyleSheet("color: green")

        self.statusBar().showMessage(msg[1])
        
    def signal_accept(self, msg):
        self.centralWidget.pbar.setValue(int(msg))
        if self.centralWidget.pbar.value() == 99:
            self.centralWidget.pbar.setValue(0)
        #    self.btn.setEnabled(True)

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
        #self.thread._db_signal.emit(1)
        query = QSqlQuery("select * from history_calls order by start_time desc")
        self.centralWidget.model.setQuery(query)

        xml_string = "<XCTIP><Calls><Change_EV><Src_Id>1001</Src_Id><Dst_Id>1001</Dst_Id><CallsState>NewCall_ST</CallsState><CR>15822</CR><Calling><Number>123123123</Number></Calling><Colp><Number>201</Number><Comment>Abonent 201</Comment></Colp><Called><Number>615555555</Number></Called></Change_EV></Calls></XCTIP>"
        
        elem = ET.fromstring(xml_string)
        #ET.dump(elem)

        change = elem.findall(".//Change_EV")
        for row in change:
            calling = row.find(".//Calling")
            if calling is not None:
                calling = calling.find(".//Number")
                print(calling.text)
            called = row.find(".//Called")
            if called is not None:
                called = called.find(".//Number")
                print(called.text)
            calls_state = row.find(".//CallsState")
            if calls_state is not None:
                print(calls_state.text)
        
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
    def __init__(self,sock):
        super(SocketThread, self).__init__()
        self.sock = sock

        #def __del__(self):
        #self.wait()

    def read_frame(self):
        self.parser.feed("<root>")

        while True:
            data = self.sock.recv(1)
            data = data.decode("utf-8")
            self.parser.feed(data)
            for event, elem in self.parser.read_events():
                if elem.tag == 'XCTIP':
                    print("READ FRAME",elem)
                    ET.dump(elem)
                    return elem

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
                    print(ET.tostring(row))
                    calling = row.find(".//Calling/Number")
                    if calling:
                        print(calling.text)
                    called = row.find(".//Called/Number")
                    if called:
                        print(called.text)
                    calls_state = row.find(".//CallsState")
                    if calls_state:
                        print(calls_state.text)

                    self._signal.emit(ET.tostring(row).encode('UTF-8'))
                    
                log = elem.findall(".//LogInfo_ANS")
                for row in log:
                    comment = row.find('Comment').text
                    self._signal.emit((FRAME_SUCCESS,comment))
            except Exception as e:
                self._signal.emit((FRAME_EXCEPTION,str(e)))


class CentralWidget(QWidget):
    def __init__(self):
        super(CentralWidget, self).__init__()
        self.btn = QPushButton('Click me')
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
        self.setup_model('history_calls')
        
        self.tableview = QTableView()
        self.tableview.setModel(self.model)
        self.setup_tableview()    

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

        self._filter,self._f = [],[]

        self.vbox = QVBoxLayout()
        self.vbox.addWidget(self.label)
        self.vbox.addWidget(line_edit)
        self.vbox.addWidget(self.all_checkbox)
        self.vbox.addWidget(self.missed_checkbox)
        self.vbox.addWidget(self.incoming_checkbox)
        self.vbox.addWidget(self.outgoing_checkbox)
        self.vbox.addWidget(self.tableview)
        self.vbox.addWidget(self.pbar)
        self.setLayout(self.vbox)
        
        self.show()

    def setup_tableview(self):
        self.tableview.hideColumn(0)
        self.tableview.hideColumn(1)
        self.tableview.hideColumn(2)
        self.tableview.hideColumn(6)
        #self.tableview.resizeColumnsToContents()
        #self.tableview.horizontalHeader().setSectionResizeMode(QtWidgets.QHeaderView.Stretch)
        self.tableview.setSortingEnabled(True)
        self.tableview.sortByColumn(4, Qt.DescendingOrder);

    def setup_model(self,table):
        self.model.setTable("history_calls")
        #query = QSqlQuery("select * from history_calls order by start_time desc")
        #self.model.setQuery(query)
        self.model.setHeaderData(3, Qt.Horizontal, "ID połączenia")
        self.model.setHeaderData(4, Qt.Horizontal, "Data i godzina")
        self.model.setHeaderData(5, Qt.Horizontal, "Typ")
        self.model.setHeaderData(6, Qt.Horizontal, "Numer")
        self.model.setHeaderData(7, Qt.Horizontal, "Długość połączenia (s)")
        self.model.setHeaderData(8, Qt.Horizontal, "Ilość prób")
        self.model.setHeaderData(9, Qt.Horizontal, "Numer")
        self.model.setHeaderData(10, Qt.Horizontal, "Abonent")
        self.model.select()

    def _build_filter(self,f,value):
        self._filter.append(f)        
        if not value:
            self._filter = list(filter((f).__ne__,self._filter))

        self.setFilter()

    def setFilter(self):
        sql = " AND ".join(self._f+self._filter)
        print(sql)
        self.model.setFilter(" AND ".join(self._f+self._filter))

    def filter_number(self,number):
        self._f = []
        if number:
            self._f = ["(cnumber like '%"+number+"%' OR cname like '%"+number+"%')",]

        self.setFilter()

    def filter_outgoing(self,value):
        _s = "h_type = 'OutCall'"
        self._build_filter(_s,value)        

    def filter_incoming(self,value):
        _s = "h_type = 'InCall'"
        self._build_filter(_s,value)

    def filter_missed(self,value):
        _s = "h_type = 'MissedCall'"
        self._build_filter(_s,value)
        
    def signal_accept(self, msg):
        self.pbar.setValue(int(msg))
        if self.pbar.value() == 99:
            self.pbar.setValue(0)
            self.btn.setEnabled(True)
            
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
