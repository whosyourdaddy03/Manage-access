import os, sys
os.environ["DISPLAY"] = ":0"
os.environ["QT_QPA_PLATFORM"] = "xcb"
sys.path.insert(0, "/mnt/d/Graduate/code")
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QTimer
import drone_platform as dp

app = QApplication([])
app.setStyleSheet(dp.QSS)
w = dp.MainWindow()
w.resize(1440, 900)
w.move(60, 20)
w.show()
w.cmb_src.setCurrentText("TCP帧流")

def report(tag):
    v = w.vals
    print(f"[{tag}] frames={w.lbl_frames.text()} range={v['range'].text()} "
          f"azim={v['azim'].text()} conf={v['conf'].text()} "
          f"status={v['status'].text()} fps={v['fps'].text()} rate={v['rate'].text()}",
          flush=True)

QTimer.singleShot(1000, lambda: (w.btn_start.click(), print("START_CLICKED", flush=True)))
for t in (16000, 22000, 28000):
    QTimer.singleShot(t, lambda tt=t: report(f"t+{tt/1000:.0f}s"))
def finish():
    w.grab().save("/mnt/d/Graduate/code/_live_shot.png")
    w._stop()
    print("GRAB_SAVED", flush=True)
    app.quit()
QTimer.singleShot(30000, finish)
app.exec()
