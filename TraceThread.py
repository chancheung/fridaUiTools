import socket
import struct
from copy import copy

from PyQt5.QtCore import *
import frida
import json
import hexdump


# 继承QThread
class Runthread(QThread):
    #  通过类成员对象定义信号对象
    #功能日志信号
    loggerSignel=pyqtSignal(str)
    #输出日志
    outloggerSignel = pyqtSignal(str)
    #线程退出信号
    taskOverSignel=pyqtSignal()

    def __init__(self,hooksData,attachName):
        super(Runthread, self).__init__()
        self.hooksData = hooksData
        self.attachName=attachName
        # self.scripts=[]
        self.script=None
        self.device=None

    def __del__(self):
        self.wait()

    def quit(self):
        self.script.unload()
        self.taskOverSignel.emit()
        # for s in copy(self.scripts):
        #     s.unload()
        #     self.scripts.remove(s)
        #     self.taskOverSignel.emit()

    def log(self,msg):
        self.loggerSignel.emit(msg)

    def outlog(self,msg):
        self.outloggerSignel.emit(msg)

    def _attach(self,pid):
        if not self.device: return
        self.log("attach '{}'".format(pid))
        session = self.device.attach(pid)
        session.enable_child_gating()
        source=""
        for item in self.hooksData:
            if item=="r0capture":
                #使用r0capture.js
                source+=open('./js/r0capture.js', 'r',encoding="utf8").read()
        # if len(source) <= 0 :
        source+=open("./js/default.js",'r',encoding="utf8").read()

        script = session.create_script(source)
        script.on("message", self.on_message)
        script.load()
        self.script=script

    def r0capture_message(self,p,data):
        if data==None or len(data) == 1:
            # print(p["function"])
            self.outlog(p["function"])
            if len(p["stack"])>0:
                self.outlog(p["stack"])
            return

        src_addr = socket.inet_ntop(socket.AF_INET,
                                    struct.pack(">I", p["src_addr"]))
        dst_addr = socket.inet_ntop(socket.AF_INET,
                                    struct.pack(">I", p["dst_addr"]))
        self.outlog("SSL Session: " + p["ssl_session_id"])
        self.outlog("[%s] %s:%d --> %s:%d" % (
            p["function"],
            src_addr,
            p["src_port"],
            dst_addr,
            p["dst_port"]))

        self.outlog(p["stack"])
        res= hexdump.hexdump(data,"return")
        self.outlog(res)

    def default_message(self,p):
        self.outlog(p["data"])

    def showMethods(self,className,methodName):
        self.script.post({'type': 'input', 'payload': {"func":"showMethods","className":className,"methodName":methodName}})
        self.log("post showMethods:"+className+","+methodName)

    def showExport(self,moduleName,methodName,isExport):
        self.script.post({'type': 'input', 'payload': {"func":"showMethods","moduleName":moduleName,"methodName":methodName,"isExport":isExport}})
        self.log("post showMethods:"+moduleName+","+methodName)

    def on_message(self,message, data):
        if message["type"] == "error":
            self.outlog(message)
            return
        if "init" in message["payload"]:
            self.outlog(message["payload"]["init"])
            self.log(message["payload"]["init"])
            return
        if message["payload"]["jsname"]=="default":
            self.default_message(message["payload"])
            return
        elif message["payload"]["jsname"]=="r0capture":
            self.r0capture_message(message["payload"],data)



    def _on_child_added(self,child):
        self._attach(child.pid)

    def run(self):
        self.device = frida.get_usb_device()
        self.device.on("child-added", self._on_child_added)
        application = self.device.get_frontmost_application()
        target = 'Gadget' if application.identifier == 're.frida.Gadget' else application.identifier
        if len(self.attachName)<=0:
            for process in self.device.enumerate_processes():
                if target == process.name:
                    self._attach(process.name)
        else:
            self._attach(self.attachName)
        print("thread over")
        # self.taskOverSignel.emit()
