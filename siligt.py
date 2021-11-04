#!/usr/bin/env python3

import sys,socket,time
from PyQt5 import QtCore
from PyQt5.QtCore import QThread, pyqtSignal,Qt
from PyQt5.QtWidgets import QWidget, QPushButton, QProgressBar, QVBoxLayout, QApplication,QStatusBar,QMainWindow,QLabel,QMenuBar,QMenu,QAction,QListWidget,QListWidgetItem,QToolBar,QToolButton,QTableView
from PyQt5 import QtGui
from PyQt5.QtGui import QIcon
from PyQt5.QtSql import QSqlDatabase, QSqlTableModel

#XML
import xml.etree.ElementTree as ET
#Thread
from sync import CallHistoryThread
#conf
from conf import silican_address


class Window(QMainWindow):
    """Main Window."""
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

    def connect(self):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.settimeout(5)
        self.sock.connect(silican_address)
        self.statusBar().showMessage('Connected to silican on socket %s:%s' %silican_address)

    def newCall(self):
        print('New')

    def login(self):
        message = b'<?xml version="1.0" encoding="IBM852"?><XCTIP><Log><MakeLog><CId>12</CId><Login>201</Login><Pass>mikran123</Pass></MakeLog></Log></XCTIP>'
        print("Logging in")
        #self.statusBar().showMessage("Logging in .......")
        #print(message.decode('utf-8'));
        self.sock.sendall(message)
        time.sleep(0.1)
        try:
            data = self.sock.recv(1024)
            data = data.decode("utf-8")
            print(data)
            root = ET.fromstring('<root>%s</root>' % data)
            if not root.findall(".//Error"):
                self.statusBar().setStyleSheet("color: green")
                self.logId = root.find(".//Id").text
                print(self.logId)
            else:
                self.statusBar().setStyleSheet("color: red")

            self.statusBar().showMessage(data)            
        except Exception as e:
            self.statusBar().setStyleSheet("color: red");
            self.statusBar().showMessage("Exception thrown: %s" % str(e))

        message = b'<?xml version="1.0" encoding="IBM852"?><XCTIP><Calls><Register_REQ><CId>1</CId><Id>1001</Id><Pass>mikran123</Pass></Register_REQ></Calls></XCTIP>'
#            message = b'<?xml version="1.0" encoding="IBM852"?><XCTIP><Sync><Sync_REQ><CId>9</CId><Marker></Marker><SyncType>HistoryCall</SyncType><Limit>5</Limit></Sync_REQ></Sync></XCTIP>'
        self.sock.sendall(message)
        time.sleep(0.5)
        try:
            data = self.sock.recv(1024)
            data = data.decode("utf-8")
            print(data)
            self.statusBar().setStyleSheet("color: green");
            self.statusBar().showMessage(data)
        except Exception as e:
            self.statusBar().setStyleSheet("color: red");
            self.statusBar().showMessage("Exception thrown: %s" % str(e))


        self.thread = CallHistoryThread()
        self.thread._signal.connect(self.signal_accept)
        self.thread.start()
        
    def signal_accept(self, msg):
        self.centralWidget.pbar.setValue(int(msg))
        if self.centralWidget.pbar.value() == 99:
            self.centralWidget.pbar.setValue(0)
        #    self.btn.setEnabled(True)

    def history(self):
        thread = CallHistoryThread()
        thread._signal.connect(self.signal_accept)
        thread.start()
        print("Thread started")
        
    def ping(self):
        message = b'<?xml version="1.0" encoding="IBM852"?><XCTIP><Stream><WDTest></WDTest></Stream></XCTIP>'
        self.sock.sendall(message)
        try:
            data = self.sock.recv(1024)
            data = data.decode("utf-8")
            self.statusBar().setStyleSheet("color: green");
            self.statusBar().showMessage(data)
        except Exception as e:
            self.statusBar().setStyleSheet("color: red");
            self.statusBar().showMessage("Exception thrown: %s" % str(e))
        
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
        # Create new action
        newAction = QAction(QIcon('new.png'), '&New', self)        
        newAction.setShortcut('Ctrl+N')
        newAction.setStatusTip('New document')
        newAction.triggered.connect(self.newCall)
        
        mainMenu = self.menuBar()
        fileMenu = mainMenu.addMenu('&File')
        fileMenu.addAction(newAction)

class Thread(QThread):
    _signal = pyqtSignal(int)
    def __init__(self,sock):
        super(Thread, self).__init__()
        self.sock = sock

    def __del__(self):
        self.wait()

    def run(self):        
        #for i in range(10):
        #    time.sleep(0.1)
        i=0
        while True:
            i = i+1
            self._signal.emit(i)
            time.sleep(1)

        #message = b'<?xml version="1.0" encoding="IBM852"?><XCTIP><Sync><Sync_REQ><CId>9</CId><Marker></Marker><SyncType>HistoryCall</SyncType><Limit>2</Limit></Sync_REQ></Sync></XCTIP>'
        #self.sock.sendall(message)

        self.sock.settimeout(None)
        while True:
            try:
                data = self.sock.recv(1024)
                data = data.decode("utf-8")
                print(data)
            except Exception as e:
                print(str(e))

class CentralWidget(QWidget):
    def __init__(self):
        super(CentralWidget, self).__init__()
        self.btn = QPushButton('Click me')
        self.btn.clicked.connect(self.btnFunc)
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
        #self.model.setHeaderData(0, Qt.Horizontal, "marker")
        #self.model.setHeaderData(1, Qt.Horizontal, "row_type")
        #self.model.setHeaderData(2, Qt.Horizontal, "sync_type")
        #self.model.setHeaderData(3, Qt.Horizontal, "h_id")
        self.model.select()

        self.tableview = QTableView()
        self.tableview.setModel(self.model)
        self.tableview.hideColumn(0)
        self.tableview.hideColumn(1)
        self.tableview.hideColumn(2)
        self.tableview.resizeColumnsToContents()

        self.vbox = QVBoxLayout()
        self.vbox.addWidget(self.btn)
        self.vbox.addWidget(self.tableview)
        self.vbox.addWidget(self.pbar)
        self.setLayout(self.vbox)
        
        self.show()

    def btnFunc(self):
        self.thread = Thread()
        self.thread._signal.connect(self.signal_accept)
        self.thread.start()
        self.btn.setEnabled(False)

    def signal_accept(self, msg):
        self.pbar.setValue(int(msg))
        if self.pbar.value() == 99:
            self.pbar.setValue(0)
            self.btn.setEnabled(True)
            
class CallsQSqlTableModel(QSqlTableModel):
   def __init__(self, dbcursor=None):
       super(CallsQSqlTableModel, self).__init__()
 
   def data(self, QModelIndex, role=None):
       v = QSqlTableModel.data(self, QModelIndex, role);
       if role == QtCore.Qt.BackgroundRole:
           return QtGui.QColor(QtCore.Qt.gray)

       if role == Qt.DisplayRole or role == Qt.EditRole:
           return "val"

       return v

if __name__ == "__main__":
    app = QApplication(sys.argv)
    ex = Window()
    ex.show()
    sys.exit(app.exec_())
