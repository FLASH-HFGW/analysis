import numpy as np
import h5py
import matplotlib.pyplot as plt
from matplotlib.widgets import Button

# =========================================
# CONFIG
# =========================================
# home = os.path.expanduser("~")
run = int(input("run number [int] "))

path = "./h5/"
fname = (path+'/run%05d.h5' % run)
initial_event = 0
initial_channel = 0

# =========================================
# LOAD HDF5
# =========================================
f = h5py.File(fname, "r")

freq = f["spec/freq_axis"][:]
has_spec = f["events/has_SPEC"][:]

fft_datasets = [
    f["spec/fft_ch0"],
    f["spec/fft_ch1"],
    f["spec/fft_ch2"],
    f["spec/fft_ch3"],
    f["spec/fft_ch4"],
    f["spec/fft_ch5"],
]

event_numbers = f["events/event"][:]
timestamps = f["events/timestamp"][:]

n_events = len(event_numbers)
n_channels = 6

# =========================================
# STATE
# =========================================
state = {
    "event_idx": initial_event,
    "channel": initial_channel,
}

# =========================================
# FIGURE
# =========================================
fig, ax = plt.subplots(figsize=(10, 6))
plt.subplots_adjust(bottom=0.22)

line, = ax.plot([], [])
ax.set_xlabel("Frequency [Hz]")
ax.set_ylabel("|rFFT|")
ax.set_yscale("log")
ax.grid(True, which="both", alpha=0.3)

title = ax.set_title("")

# =========================================
# HELPERS
# =========================================
def get_fft(event_idx, ch):
    return fft_datasets[ch][event_idx, :]

def update_plot():
    i = state["event_idx"]
    ch = state["channel"]

    fft = get_fft(i, ch)

    ax.clear()
    ax.plot(freq, fft)
    ax.set_xlabel("Frequency [Hz]")
    ax.set_ylabel("|rFFT|")
    ax.set_yscale("log")
    ax.grid(True, which="both", alpha=0.3)

    evnum = event_numbers[i]
    ts = timestamps[i]
    spec_ok = int(has_spec[i])

    ax.set_title(
        f"File: {fname}\n"
        f"Event index = {i} | Event number = {evnum} | Channel = {ch} | has_SPEC = {spec_ok} | timestamp = {ts}"
    )

    # opzionale: limita x al Nyquist
    ax.set_xlim(freq[0], freq[-1])

    # evita problemi con eventuali NaN o zeri
    finite = np.isfinite(fft) & (fft > 0)
    if np.any(finite):
        ymin = np.min(fft[finite])
        ymax = np.max(fft[finite])
        ax.set_ylim(max(ymin * 0.8, 1e-12), ymax * 1.2)

    fig.canvas.draw_idle()

def next_event(event):
    state["event_idx"] = min(state["event_idx"] + 1, n_events - 1)
    update_plot()

def prev_event(event):
    state["event_idx"] = max(state["event_idx"] - 1, 0)
    update_plot()

def next_channel(event):
    state["channel"] = min(state["channel"] + 1, n_channels - 1)
    update_plot()

def prev_channel(event):
    state["channel"] = max(state["channel"] - 1, 0)
    update_plot()

def on_key(event):
    if event.key == "right":
        next_event(None)
    elif event.key == "left":
        prev_event(None)
    elif event.key == "up":
        next_channel(None)
    elif event.key == "down":
        prev_channel(None)

# =========================================
# BUTTONS
# =========================================
ax_prev_ev = plt.axes([0.10, 0.08, 0.15, 0.06])
ax_next_ev = plt.axes([0.27, 0.08, 0.15, 0.06])
ax_prev_ch = plt.axes([0.55, 0.08, 0.15, 0.06])
ax_next_ch = plt.axes([0.72, 0.08, 0.15, 0.06])

btn_prev_ev = Button(ax_prev_ev, "Prev Event")
btn_next_ev = Button(ax_next_ev, "Next Event")
btn_prev_ch = Button(ax_prev_ch, "Prev Channel")
btn_next_ch = Button(ax_next_ch, "Next Channel")

btn_prev_ev.on_clicked(prev_event)
btn_next_ev.on_clicked(next_event)
btn_prev_ch.on_clicked(prev_channel)
btn_next_ch.on_clicked(next_channel)

fig.canvas.mpl_connect("key_press_event", on_key)

# =========================================
# START
# =========================================
update_plot()
plt.show()

# =========================================
# CLOSE FILE AFTER WINDOW IS CLOSED
# =========================================
f.close()