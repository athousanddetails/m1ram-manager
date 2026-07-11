import lldb

LOG = "/tmp/m1ram_hid_capture.log"
_log = open(LOG, "w")


def _dump(frame, kind):
    t = frame.reg["x1"].GetValueAsUnsigned()
    rid = frame.reg["x2"].GetValueAsUnsigned()
    ptr = frame.reg["x3"].GetValueAsUnsigned()
    ln = frame.reg["x4"].GetValueAsSigned()
    err = lldb.SBError()
    data = b""
    if ptr and 0 < ln <= 512:
        data = frame.thread.process.ReadMemory(ptr, ln, err) or b""
    line = f"{kind} type={t} id={rid:#04x} len={ln} : {data.hex(' ')}"
    _log.write(line + "\n")
    _log.flush()
    print(line)


def on_set(frame, bp_loc, _dict):
    _dump(frame, "SET")
    return False


def on_get(frame, bp_loc, _dict):

    _dump(frame, "GET")
    return False


def __lldb_init_module(debugger, _dict):
    t = debugger.GetSelectedTarget()
    for sym, cb in (
        ("IOHIDDeviceSetReport", "capture_hid.on_set"),
        ("IOHIDDeviceGetReport", "capture_hid.on_get"),
    ):
        bp = t.BreakpointCreateByName(sym)
        bp.SetScriptCallbackFunction(cb)
        print(f"breakpoint on {sym}: {bp.GetNumLocations()} location(s)")
    print(f"logging HID traffic to {LOG}")
