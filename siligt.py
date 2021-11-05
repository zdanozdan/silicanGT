#!/usr/bin/env python3

import sys,socket,time
from PyQt5 import QtCore
from PyQt5.QtCore import QThread, pyqtSignal,Qt
from PyQt5.QtWidgets import QWidget, QPushButton, QProgressBar, QVBoxLayout, QApplication,QStatusBar,QMainWindow,QLabel,QMenuBar,QMenu,QAction,QToolBar,QToolButton,QTableView
from PyQt5 import QtWidgets
from PyQt5 import QtGui
from PyQt5.QtGui import QIcon
from PyQt5.QtSql import QSqlDatabase, QSqlTableModel

#XML
import xml.etree.ElementTree as ET
#Thread
from sync import CallHistoryThread
#conf
from conf import silican_address

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

        self.connect()

        self.thread = CallHistoryThread()
        self.thread._signal.connect(self.signal_accept)
        self.thread._db_signal.connect(self.signal_sync_db)

        self.socketthread = SocketThread(self.sock)
        self.socketthread._signal.connect(self.signal_status)

        self.socketthread.start()
        self.thread.start()

        self.login()

    def connect(self):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.connect(silican_address)
        self.statusBar().showMessage('Connected to silican on socket %s:%s' %silican_address)

    def send_socket(self,msg):
        try:
            self.sock.sendall(msg)
        except Exception as e:
            self.statusBar().setStyleSheet("color: red")
            self.statusBar().showMessage(str(e))

    def login(self):
        message = b'<?xml version="1.0" encoding="IBM852"?><XCTIP><Log><MakeLog><CId>12</CId><Login>201</Login><Pass>mikran123</Pass></MakeLog></Log></XCTIP>'
        self.send_socket(message)
        self.register_calls()

    def register_calls(self):
        message = b'<?xml version="1.0" encoding="IBM852"?><XCTIP><Calls><Register_REQ><CId>1</CId><Id>1001</Id><Pass>mikran123</Pass></Register_REQ></Calls></XCTIP>'
        self.send_socket(message)

    def signal_sync_db(self,msg):
        self.centralWidget.model.select()
        print(msg,"signal_sync_db")

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

    def history(self):
        self.thread._db_signal.emit(1)

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

        toolButton = QToolButton()
        toolButton.setText("Login")
        toolButton.clicked.connect(self.login)
        self.toolBar.addWidget(toolButton)

        toolButton = QToolButton()
        toolButton.setText("Ping")
        toolButton.clicked.connect(self.ping)
        self.toolBar.addWidget(toolButton)

        toolButton = QToolButton()
        toolButton.setText("History")
        toolButton.clicked.connect(self.history)
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
        self.model.setTable("history_calls")  
        #self.model.setEditStrategy(QSqlTableModel.OnFieldChange)
        self.model.setHeaderData(3, Qt.Horizontal, "ID połączenia")
        self.model.setHeaderData(4, Qt.Horizontal, "Data i godzina")
        self.model.setHeaderData(5, Qt.Horizontal, "Typ")
        self.model.setHeaderData(6, Qt.Horizontal, "Numer")
        self.model.setHeaderData(7, Qt.Horizontal, "Długość połączenia (s)")
        self.model.setHeaderData(8, Qt.Horizontal, "Ilość prób")
        #self.model.select()

        self.tableview = QTableView()
        self.tableview.setModel(self.model)
        self.tableview.hideColumn(0)
        self.tableview.hideColumn(1)
        self.tableview.hideColumn(2)
        self.tableview.resizeColumnsToContents()
        #self.tableview.horizontalHeader().setStretchLastSection(True)
        self.tableview.horizontalHeader().setSectionResizeMode(QtWidgets.QHeaderView.Stretch)
        #self.tableview.setMinimumWidth(25);
        self.tableview.setSortingEnabled(True)
        self.tableview.sortByColumn(0, Qt.DescendingOrder);

        #self.model.select()

        # filter proxy model
        filter_proxy_model = QtCore.QSortFilterProxyModel()
        filter_proxy_model.setSourceModel(self.model)
        filter_proxy_model.setFilterKeyColumn(6) # sixth column

        line_edit = QtWidgets.QLineEdit()
        line_edit.textChanged.connect(filter_proxy_model.setFilterRegExp)

        missed_checkbox = QtWidgets.QCheckBox("Nieodebrane")
        incoming_checkbox = QtWidgets.QCheckBox("Przychodzące")
        outgoing_checkbox = QtWidgets.QCheckBox("Wychodzące")

        self.vbox = QVBoxLayout()
        self.vbox.addWidget(self.label)
        self.vbox.addWidget(line_edit)
        self.vbox.addWidget(missed_checkbox)
        self.vbox.addWidget(incoming_checkbox)
        self.vbox.addWidget(outgoing_checkbox)
        self.vbox.addWidget(self.tableview)
        self.vbox.addWidget(self.pbar)
        self.setLayout(self.vbox)
        
        self.show()

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
           #return QtGui.QColor(QtCore.Qt.gray)
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
