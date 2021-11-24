#!/usr/bin/env python3

import sys,socket,time
from PyQt5 import QtCore
from PyQt5.QtCore import QThread, pyqtSignal,Qt
from PyQt5.QtWidgets import QWidget, QTabWidget, QPushButton, QProgressBar, QVBoxLayout, QHBoxLayout, QFormLayout, QLineEdit, QApplication,QStatusBar,QMainWindow,QLabel,QMenuBar,QMenu,QAction,QToolBar,QToolButton,QTableView,QMessageBox,QDialog,QFrame
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

FRAME_SUCCESS,NEW_CONNECTION = 0,0
FRAME_EXCEPTION,RELEASE_CONNECTION = 1,1

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


        self.con.close()
        del self.con

        #start threads
        self.start()

    def connect(self):
        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock.settimeout(3)
            self.sock.connect((self.silican_address,self.silican_port))
            self.sock.settimeout(None)
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
        self.socketthread._signal_connection.connect(self.centralWidget.signal_connection)
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
        toolButton.clicked.connect(self.centralWidget.my_test)
        self.toolBar.addWidget(toolButton)

        toolButton = QToolButton()
        toolButton.setText("Settings")
        toolButton.clicked.connect(self.settings)
        self.toolBar.addWidget(toolButton)

    def createMenuBar(self):
        cleanAction = QAction(QIcon('new.png'), '&Wyczyść bieżące', self)
        cleanAction.setShortcut('Ctrl+W')
        cleanAction.setStatusTip('Wyczyść bieżącą historię')
        cleanAction.triggered.connect(self.cleanAction)
        
        mainMenu = self.menuBar()
        fileMenu = mainMenu.addMenu('&File')
        fileMenu.addAction(cleanAction)

    def cleanAction(self):
        QMessageBox.critical(
            None,
            "TBD",
            "Do zrobienia",
        )

class SocketThread(QThread):
    _signal = pyqtSignal(tuple)
    _db_signal = pyqtSignal(tuple)
    _signal_connection = pyqtSignal(tuple)
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
                    calls_state = row.find(".//CallsState").text
                    cr = row.find(".//CR").text

                    calling = 0
                    if row.find(".//Calling/Number") is not None:
                        calling = row.find(".//Calling/Number").text

                    called = 0
                    if row.find(".//Called/Number") is not None:
                        called = row.find(".//Called/Number").text

                    data = (cr,datetime.now().strftime("%m-%d-%Y, %H:%M:%S"),calls_state,calling,called)

                    #CREATE TABLE IF NOT EXISTS current_calls ( cr INTEGER PRIMARY KEY, start_time TEXT, calls_state var_char(255), calling_number varchar(255), called_number 
                    try:
                        c.execute("INSERT INTO current_calls VALUES (?,?,?,?,?)", data)
                        conn.commit()
                        self._db_signal.emit(data)
                        self._signal.emit((FRAME_SUCCESS, "Nowe połączenie: %s" % calling))
                        self._signal_connection.emit((NEW_CONNECTION,"%s" % calling))
                    except sqlite3.IntegrityError as e:
                        data = (calls_state,datetime.now().strftime("%m-%d-%Y, %H:%M:%S"),cr)
                        c.execute("UPDATE current_calls SET calls_state = ?, start_time = ? WHERE cr = ?", data)
                        conn.commit()
                        self._db_signal.emit(data)
                        self._signal.emit((FRAME_SUCCESS, "Połącznie zakończone"))
                        self._signal_connection.emit((RELEASE_CONNECTION,'0'))
                    
                log = elem.findall(".//LogInfo_ANS")
                for row in log:
                    comment = row.find('Comment').text
                    self._signal.emit((FRAME_SUCCESS,comment))
                    
            except Exception as e:
                self._signal.emit((FRAME_EXCEPTION,str(e)))
                QMessageBox.critical(
                    None,
                    "Error!",
                    "Error: %s" % str(e),
                )
                


class CentralWidget(QWidget):
    def __init__(self):
        super(CentralWidget, self).__init__()
        self.label = QLabel("Czekam na nowe połączenie ....")
        font = self.label.font()
        font.setPointSize(30)
        self.label.setFont(font)
        self.label.setAlignment(Qt.AlignHCenter | Qt.AlignVCenter)
        self.label.setStyleSheet("color: gray")

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

        self._filter,self._f = [],[]

        self.tabs = QTabWidget()
        self.tab1 = QWidget()
        self.tab2 = QWidget()
        self.tabs.addTab(self.tab1,"Bieżące połączenia")
        self.tabs.addTab(self.tab2,"Historyczne")

        self.current_model = CallsQSqlTableModel(self)
        self.setup_current_model(self.current_model,"current_calls")

        self.tableview_current = MyTableView()
        self.tableview_current.setModel(self.current_model)
        self.tableview_current.resizeColumnsToContents()
        self.tableview_current.horizontalHeader().setSectionResizeMode(QtWidgets.QHeaderView.Stretch)
        self.tableview_current.sortByColumn(1, Qt.DescendingOrder);
        self.tableview_current.setSortingEnabled(True)

        layout1 = QVBoxLayout()
        layout1.addWidget(self.tableview_current)
        self.tab1.setLayout(layout1)

        hbox = QHBoxLayout()
        hbox.addWidget(self.all_checkbox)
        hbox.addWidget(self.missed_checkbox)
        hbox.addWidget(self.incoming_checkbox)
        hbox.addWidget(self.outgoing_checkbox)

        line = QFrame()
        line.resize(300,300)
        line.setStyleSheet("background-color: rgb(200, 255, 255)")
        
        layout2 = QVBoxLayout()
        layout2.addLayout(hbox)
        layout2.addWidget(self.tableview)
        self.tab2.setLayout(layout2)

        self.vbox = QVBoxLayout()
        self.vbox.addWidget(self.label)
        self.vbox.addWidget(line_edit)
        #self.vbox.addLayout(hbox)
        self.vbox.addWidget(self.tabs)
        self.vbox.addWidget(self.pbar)

        self.setLayout(self.vbox)
        
        self.show()

    def my_test(self):
        self.setup_model(self.model,'history_calls')
        self.model.select()
        self.setup_tableview()
        self.label.setText("@@@@")

    def signal_connection(self,_tuple):
        if _tuple[0] == NEW_CONNECTION:
            self.label.setStyleSheet("color: green")
            self.label.setText("Nowe połączenie: %s" % _tuple[1])
            self._calling_number = _tuple[1]
        else:
            self.label.setText("Zakończono: %s" % self._calling_number)
            self.label.setStyleSheet("color: gray")

    def signal_sync_db(self,_tuple):
        self.setup_model(self.model,'history_calls')
        self.model.select()
        self.setup_tableview()

    def signal_sync(self,_tuple):
        self.setup_current_model(self.current_model,"current_calls")
        self.tableview_current.setModel(self.current_model)
        self.tableview_current.sortByColumn(1, Qt.DescendingOrder);
        
    def setup_tableview(self):
        self.tableview.hideColumn(0)
        self.tableview.hideColumn(1)
        self.tableview.hideColumn(2)
        self.tableview.hideColumn(6)
        self.tableview.resizeColumnsToContents()
        self.tableview.horizontalHeader().setSectionResizeMode(QtWidgets.QHeaderView.Stretch)
        self.tableview.setSortingEnabled(True)
        self.tableview.sortByColumn(4, Qt.DescendingOrder);

    def setup_current_model(self,model,table):
        model.setTable(table)
        model.setHeaderData(0, Qt.Horizontal, "ID połączenia")
        model.setHeaderData(1, Qt.Horizontal, "Data i godzina")
        model.setHeaderData(2, Qt.Horizontal, "Typ")
        model.setHeaderData(3, Qt.Horizontal, "Numer")
        model.setHeaderData(4, Qt.Horizontal, "Numer wew")
        model.select()

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
        self.model.setFilter(" AND ".join(self._f+self._filter))

    def filter_number(self,number):
        self._f = []
        if number:
            self._f = ["(cnumber like '%"+number+"%' OR cname like '%"+number+"%')",]

        self.setFilter()
        self.current_model.setFilter("calling_number like '%"+number+"%' OR called_number like '%"+number+"%'")

    def filter_outgoing(self,value):
        _s = "h_type = 'OutCall'"
        self._build_filter(_s,value)

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
           if v == 'NewCall_ST':
               self._color = QtCore.Qt.green
               return "Nowe"
           if v == 'Release_ST':
               #self._color = QtCore.Qt.yellow
               return "Zakończone"
               
       return v
   
class MyTableView(QtWidgets.QTableView):
    def keyPressEvent(self, event):
        if event.key() == QtCore.Qt.Key_Delete or event.key() == QtCore.Qt.Key_Backspace:
            self.model().removeRow(self.currentIndex().row())
            QMessageBox.critical(
                None,
                "Delete",
                "Usunięto rekord na pozycji %d" % self.currentIndex().row(),
            )
        super(MyTableView, self).keyPressEvent(event)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    ex = Window()
    ex.show()
    sys.exit(app.exec_())
