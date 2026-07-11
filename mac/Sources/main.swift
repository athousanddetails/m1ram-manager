import SwiftUI
import IOKit
import IOKit.hid
import UniformTypeIdentifiers

enum M1 {
    static let CARD_SIZE = 32768
    static let VID: Int = 0x16C0, PID: Int = 0x1770
    static let REPORT = 0x14
    static let SUB_SETADDR: UInt8 = 0x01, SUB_WRITE: UInt8 = 0x02
    static let REPORT_ACK = 0x15, REPORT_STATUS = 0x16
    static let WRITE_CHUNK = 60, READ_CHUNK = 64
    static let RAM_MARKER: UInt8 = 0x11
    static let GLOBAL_OFF = 16, GLOBAL_LEN = 1225
    static let COMBI_OFF = 1241, COMBI_LEN = 12400
    static let PROG_OFF = 13641, PROG_LEN = 14300
    static let COMBI_REC = 124, N_COMBI = 100
    static let TIMBRE_PTRS = [36,47,58,69,80,91,102,113]
    static let TIMBRE_BIAS: UInt8 = 100
    static let F_PROG: UInt8 = 0x4C, F_COMBI: UInt8 = 0x4D
    static let GLOBAL_TEMPLATE_B64 = "AAABAAEAAAABBwAAAAAAAM4AAAAAAADOAQAAGAUAGAAAAAABABoFABoAAAAAAgAcBQAcAAAAAAMAHQUAHQAAAAAEAB8FAB8AAAAABQAhBQAhAAAAAAYAIwUAIwAAAAAHACQHACQAAAAACAAmAxQnAAAAAAkAKAcUKgAAAAAKACkEACkAAAAACwArBAArAAAAAAwALQQALQAAAAANAC8EAC8AAAAADgAwBwAwAADdAA8AMgJGMgAAAAAQADQIADQAAAAAEQA1ASg1AAAAABIANwkANwAAAAATADkGADkAAAAAFAA7BgA7AAAAABUAPAYAPAAAAAAdAD4FAD4AAAAAFwBABQBAAAAAABgAQQEAQQAAAAAZAEMJAEMAAAAAGgBFBABFAAAAABsARwEARwAAAAAcAEgJAEgAAAAAFgBUBbBXAAAAAAAAGAUAGQAAEQAFABoF7BoAAAAAGgAcCBQe3wAAAAoAHQIAHfEAAAALAB8CAB8AAOoACgAeAgAeAADzAAIAGQXYGQAAAQAGABsF9hvdAAAACAAmAuwlAAAAAAkALAUoLmMAAAAJADAIHi4AAAAACgAyBwAyAADtAAsAIAIAIAAAnQAPADQD9jkAAAAADwA1BwA1AAAAABAANwfsLwAAAAAQADYFADYAAAAAEQA4AABEAAAAABEAOQIAOQAAAAASADoKAEYAAAAAEgA7CB48AABjABMAPAYAPAAAAAAUAD8E2EHrAGMAFQBACABA5wCdABUAQQcAQWMAAAAXAEID2EIAAAAAFgBKBRRMAAAAABwASwT2QgAAAAAkAEwHAE4AAOQAHABzBSh7AADDAAAAGAUAGewADAAHABkFKBsAABQABgAaBQAaRgAAABQAGwgyGu0AAAAIAB0KAB4jAAAACgAeCPYdxwAAABoAIAUeJDIAAAAJACEFACEAAAAACwAiCeIh1gAAAAkAJAD2IgAAAAAOACUAAB4yAM4ADgAmCOwkAADmABcAKAn2J80AIAAWACkKADXOAAAADwAqAAAqAAAAABYALQXsMOIAAAAQAC4AAC4AAAAAFgAwAOIqzgAyACEAOwXYOwAAYwAgAEIF7EUAAAAAEwA9BQBCAAAAAB0ARwXsSgAAAAAeAE4F7FAAAAAAAgBIBQBIYwAIAAMASgUATGMAAAAEAEwFAExjAAAAGABUBQBUAAAAAP//DAUADAAAAAD//w0FAA0AAAAA//8OBQAOAAAAAP//MAUAMAAAAAD//zIFADIAAAAA//80BQA0AAAAAP//NQUANQAAAAD//zcFADcAAAAA//85BQA5AAAAAP//OwUAOwAAAAD//zwFADwAAAAA//8+BQA+AAAAAP//QAUAQAAAAAD//0EFAEEAAAAA//9DBQBDAAAAAP//RQUARQAAAAD//0cFAEcAAAAA//9IBQBIAAAAAP//SgUASgAAAAD//0wFAEwAAAAA//9NBQBNAAAAAP//TwUATwAAAAD//1EFAFEAAAAA//9TBQBTAAAAAP//VAUAVAAAAAD//1YFAFYAAAAA//9YBQBYAAAAAP//WQUAWQAAAAD//1sFAFsAAAAA//9dBQBdAAAAAP//XwUAXwAAAAD//2AFAGAAAAAA//9iBQBiAAAAAA=="
}

enum ConvError: LocalizedError {
    case missingBlocks(String)
    case badSize(String)
    var errorDescription: String? {
        switch self { case .missingBlocks(let s): return s; case .badSize(let s): return s }
    }
}

func korgUnpack(_ data: [UInt8]) -> [UInt8] {
    var out = [UInt8](); out.reserveCapacity(data.count * 7 / 8 + 8)
    var i = 0
    while i < data.count {
        let msb = data[i]; i += 1
        for k in 0..<7 {
            if i >= data.count { break }
            var b = data[i]; i += 1
            if (msb & (1 << k)) != 0 { b |= 0x80 }
            out.append(b)
        }
    }
    return out
}

func parseSyx(_ raw: [UInt8]) -> [UInt8: [UInt8]] {
    var blocks = [UInt8: [UInt8]](); var i = 0
    while i < raw.count {
        if raw[i] != 0xF0 { i += 1; continue }
        guard let j = raw[i...].firstIndex(of: 0xF7) else { break }
        let seg = Array(raw[i...j])
        if seg.count >= 6 && seg[1] == 0x42 && seg[3] == 0x19 {
            let fn = seg[4]
            if blocks[fn] == nil { blocks[fn] = korgUnpack(Array(seg[6..<(seg.count-1)])) }
        }
        i = j + 1
    }
    return blocks
}

func buildCard(_ urls: [URL]) throws -> [UInt8] {
    var b = [UInt8: [UInt8]]()
    for u in urls {
        let raw = [UInt8](try Data(contentsOf: u))
        for (fn, payload) in parseSyx(raw) where b[fn] == nil { b[fn] = payload }
    }
    guard let prog = b[M1.F_PROG], let combi = b[M1.F_COMBI] else {
        throw ConvError.missingBlocks("The file(s) must contain all-programs (0x4C) and all-combinations (0x4D) dumps. Found: " +
            b.keys.map { String(format: "0x%02X", $0) }.joined(separator: ", "))
    }
    guard prog.count == M1.PROG_LEN else { throw ConvError.badSize("program block \(prog.count) != \(M1.PROG_LEN)") }
    guard combi.count == M1.COMBI_LEN else { throw ConvError.badSize("combi block \(combi.count) != \(M1.COMBI_LEN)") }

    var card = [UInt8](repeating: 0, count: M1.CARD_SIZE)
    card[0] = 0x4B; card[1] = 0x4F; card[2] = 0x52; card[3] = 0x47; card[4] = 0x10
    if let t = Data(base64Encoded: M1.GLOBAL_TEMPLATE_B64) {
        for (i, v) in t.prefix(M1.GLOBAL_LEN).enumerated() { card[M1.GLOBAL_OFF + i] = v }
    }
    for i in 0..<M1.PROG_LEN { card[M1.PROG_OFF + i] = prog[i] }
    var cb = combi
    for n in 0..<M1.N_COMBI {
        let base = n * M1.COMBI_REC
        for off in M1.TIMBRE_PTRS { cb[base + off] = cb[base + off] &+ M1.TIMBRE_BIAS }
    }
    for i in 0..<M1.COMBI_LEN { card[M1.COMBI_OFF + i] = cb[i] }
    return card
}

func buildCardFromBlocks(_ prog: [UInt8], _ combi: [UInt8]) -> [UInt8] {
    var card = [UInt8](repeating: 0, count: M1.CARD_SIZE)
    card[0] = 0x4B; card[1] = 0x4F; card[2] = 0x52; card[3] = 0x47; card[4] = 0x10
    if let t = Data(base64Encoded: M1.GLOBAL_TEMPLATE_B64) {
        for (i, v) in t.prefix(M1.GLOBAL_LEN).enumerated() { card[M1.GLOBAL_OFF + i] = v }
    }
    for i in 0..<M1.PROG_LEN { card[M1.PROG_OFF + i] = prog[i] }
    var cb = combi
    for n in 0..<M1.N_COMBI {
        let base = n * M1.COMBI_REC
        for off in M1.TIMBRE_PTRS { cb[base + off] = cb[base + off] &+ M1.TIMBRE_BIAS }
    }
    for i in 0..<M1.COMBI_LEN { card[M1.COMBI_OFF + i] = cb[i] }
    return card
}

func recName(_ rec: ArraySlice<UInt8>) -> String {
    String(rec.prefix(10).map { (32...126).contains($0) ? Character(UnicodeScalar($0)) : " " })
        .trimmingCharacters(in: .whitespaces)
}

func cardPresetNames(_ img: [UInt8]) -> (programs: [String], combis: [String]) {
    var p = [String](), c = [String]()
    for i in 0..<M1.N_COMBI {
        let o = M1.PROG_OFF + i*M1.PROG_LEN/M1.N_COMBI; _ = o
        p.append(recName(img[(M1.PROG_OFF+i*143)..<(M1.PROG_OFF+i*143+10)]))
        c.append(recName(img[(M1.COMBI_OFF+i*124)..<(M1.COMBI_OFF+i*124+10)]))
    }
    return (p, c)
}

let T_OFFS = [36,47,58,69,80,91,102,113]

final class Bank {
    let url: URL, title: String
    let progs: [[UInt8]], combis: [[UInt8]]
    init(_ url: URL) throws {
        self.url = url; self.title = url.deletingPathExtension().lastPathComponent
        let b = parseSyx([UInt8](try Data(contentsOf: url)))
        guard let p = b[M1.F_PROG], let cm = b[M1.F_COMBI], p.count == M1.PROG_LEN, cm.count == M1.COMBI_LEN
        else { throw ConvError.missingBlocks("\(title): not a full bank (needs all-programs + all-combis)") }
        progs  = (0..<100).map { Array(p[$0*143..<($0*143+143)]) }
        combis = (0..<100).map { Array(cm[$0*124..<($0*124+124)]) }
    }
    func progName(_ i: Int) -> String  { recName(progs[i][0..<10]) }
    func combiName(_ i: Int) -> String { recName(combis[i][0..<10]) }
    func combiTimbres(_ i: Int) -> [(Int, Int)] {
        let rec = combis[i]
        return T_OFFS.enumerated().compactMap { (t, off) in (rec[off+10] & 0x10) == 0 ? (t, Int(rec[off])) : nil }
    }
}

final class Builder {
    private(set) var progs: [[UInt8]] = []
    private(set) var combis: [[UInt8]] = []
    private var progSrc: [String: Int] = [:]
    private(set) var warnings: [String] = []

    var progCount: Int { progs.count }
    var combiCount: Int { combis.count }

    @discardableResult
    private func addProg(_ bank: Bank, _ idx: Int) -> Int? {
        let key = "\(bank.url.path)#\(idx)"
        if let s = progSrc[key] { return s }
        if progs.count >= 100 { warnings.append("program slots full; '\(bank.progName(idx))' dropped"); return nil }
        let slot = progs.count; progs.append(bank.progs[idx]); progSrc[key] = slot; return slot
    }

    func addProgram(_ bank: Bank, _ idx: Int) { addProg(bank, idx) }

    func addCombi(_ bank: Bank, _ idx: Int) {
        if combis.count >= 100 { warnings.append("combi slots full; '\(bank.combiName(idx))' dropped"); return }
        var rec = bank.combis[idx]
        for (t, srcProg) in bank.combiTimbres(idx) {
            if let slot = addProg(bank, srcProg) { rec[T_OFFS[t]] = UInt8(slot) }
        }
        combis.append(rec)
    }

    func reset() { progs = []; combis = []; progSrc = [:]; warnings = [] }

    func image() -> [UInt8] {
        let initProg = progs.first ?? [UInt8](repeating: 0, count: 143)
        let initCombi = [UInt8](repeating: 0, count: 124)
        var pb = [UInt8](); pb.reserveCapacity(M1.PROG_LEN)
        var cb = [UInt8](); cb.reserveCapacity(M1.COMBI_LEN)
        for i in 0..<100 { pb += (i < progs.count ? progs[i] : initProg) }
        for i in 0..<100 { cb += (i < combis.count ? combis[i] : initCombi) }
        return buildCardFromBlocks(pb, cb)
    }
}

enum CardError: LocalizedError {
    case notFound, openFailed, io(String), verify(Int, Int), writeProtected
    var errorDescription: String? {
        switch self {
        case .notFound: return "No m1RAM card found on USB. Plug it in directly (not through a hub/dock) with a data cable."
        case .openFailed: return "Found the card but could not open it (permissions? another app using it?)."
        case .io(let s): return "USB error: \(s)"
        case .verify(let n, let first): return "Verify failed: \(n) bytes differ (first at \(first))."
        case .writeProtected: return "Card is WRITE-PROTECTED — flip the write-protect switch on the card, then try again."
        }
    }
}

final class CardIO {
    private var device: IOHIDDevice?
    private var manager: IOHIDManager?

    func connect() throws {
        let mgr = IOHIDManagerCreate(kCFAllocatorDefault, IOOptionBits(kIOHIDOptionsTypeNone))
        let match: [String: Any] = [kIOHIDVendorIDKey: M1.VID, kIOHIDProductIDKey: M1.PID]
        IOHIDManagerSetDeviceMatching(mgr, match as CFDictionary)
        if IOHIDManagerOpen(mgr, IOOptionBits(kIOHIDOptionsTypeNone)) != kIOReturnSuccess { throw CardError.openFailed }
        guard let set = IOHIDManagerCopyDevices(mgr) as? Set<IOHIDDevice>, let dev = set.first else {
            IOHIDManagerClose(mgr, IOOptionBits(kIOHIDOptionsTypeNone)); throw CardError.notFound
        }
        if IOHIDDeviceOpen(dev, IOOptionBits(kIOHIDOptionsTypeNone)) != kIOReturnSuccess {
            IOHIDManagerClose(mgr, IOOptionBits(kIOHIDOptionsTypeNone)); throw CardError.openFailed
        }
        manager = mgr
        device = dev
    }

    func disconnect() {
        if let dev = device { IOHIDDeviceClose(dev, IOOptionBits(kIOHIDOptionsTypeNone)) }
        if let mgr = manager { IOHIDManagerClose(mgr, IOOptionBits(kIOHIDOptionsTypeNone)) }
        device = nil; manager = nil
    }

    static func cardPresent() -> Bool {
        guard let matching = IOServiceMatching("IOUSBHostDevice") as NSMutableDictionary? else { return false }
        matching["idVendor"] = M1.VID
        matching["idProduct"] = M1.PID
        var iter: io_iterator_t = 0
        guard IOServiceGetMatchingServices(kIOMainPortDefault, matching, &iter) == KERN_SUCCESS else { return false }
        var found = false
        var svc = IOIteratorNext(iter)
        while svc != 0 { found = true; IOObjectRelease(svc); svc = IOIteratorNext(iter) }
        IOObjectRelease(iter)
        return found
    }

    private func setReport(_ reportID: Int, _ payload: [UInt8]) throws {
        guard let dev = device else { throw CardError.openFailed }
        let r = payload.withUnsafeBufferPointer {
            IOHIDDeviceSetReport(dev, kIOHIDReportTypeInput, CFIndex(reportID), $0.baseAddress!, CFIndex(payload.count))
        }
        if r != kIOReturnSuccess { throw CardError.io(String(format: "SetReport 0x%X -> 0x%08X", reportID, r)) }
    }

    @discardableResult
    private func getReport(_ reportID: Int, _ length: Int) throws -> [UInt8] {
        guard let dev = device else { throw CardError.openFailed }
        var buf = [UInt8](repeating: 0, count: length)
        var len = CFIndex(length)
        let r = buf.withUnsafeMutableBufferPointer {
            IOHIDDeviceGetReport(dev, kIOHIDReportTypeFeature, CFIndex(reportID), $0.baseAddress!, &len)
        }
        if r != kIOReturnSuccess { throw CardError.io(String(format: "GetReport 0x%X -> 0x%08X", reportID, r)) }
        return Array(buf.prefix(Int(len)))
    }

    func status() throws -> [UInt8] { try getReport(M1.REPORT_STATUS, 8) }

    private func setAddr(_ blk: Int) throws {
        try setReport(M1.REPORT, [UInt8(M1.REPORT), M1.SUB_SETADDR, UInt8((blk >> 8) & 0xFF), UInt8(blk & 0xFF)])
    }

    static let PACE_US: UInt32 = 200
    private func pace() { if CardIO.PACE_US > 0 { usleep(CardIO.PACE_US) } }

    private func readBlock(_ blk: Int, _ addrDelayUs: UInt32 = 6000) throws -> [UInt8] {
        try setAddr(blk); usleep(addrDelayUs)
        let r = Array(try getReport(M1.REPORT, M1.READ_CHUNK).prefix(M1.READ_CHUNK)); usleep(600)
        return r
    }

    @discardableResult
    private func warmup(_ addrDelayUs: UInt32) -> Bool {
        for _ in 0..<40 {
            if let r = try? readBlock(0, addrDelayUs), r.first == 0x4B { return true }
            usleep(40000)
        }
        return false
    }

    private func readOnce(_ addrDelayUs: UInt32, _ progress: ((Double) -> Void)?) throws -> [UInt8] {
        var out = [UInt8](); out.reserveCapacity(M1.CARD_SIZE)
        let n = M1.CARD_SIZE / M1.READ_CHUNK
        for blk in 0..<n {
            out.append(contentsOf: try readBlock(blk, addrDelayUs))
            if blk % 16 == 0 { progress?(Double(blk) / Double(n)) }
        }
        return Array(out.prefix(M1.CARD_SIZE))
    }

    func read(progress: ((Double) -> Void)? = nil) throws -> [UInt8] {
        var last=[UInt8](repeating:0xFF,count:M1.CARD_SIZE)
        for delay: UInt32 in [5000, 12000, 30000, 70000] {
            warmup(delay)
            let img=try readOnce(delay, progress)
            if Array(img.prefix(4))==[0x4B,0x4F,0x52,0x47] { return img }
            last=img
        }
        return last
    }

    private let nWriteBlocks = (M1.CARD_SIZE + M1.WRITE_CHUNK - 1) / M1.WRITE_CHUNK
    private func writeBlock(_ blk: Int, _ img: [UInt8]) throws {
        let lo = blk * M1.WRITE_CHUNK, hi = min(lo + M1.WRITE_CHUNK, M1.CARD_SIZE)
        var chunk = Array(img[lo..<hi])
        if chunk.count < M1.WRITE_CHUNK { chunk += [UInt8](repeating: 0, count: M1.WRITE_CHUNK - chunk.count) }
        try setReport(M1.REPORT, [UInt8(M1.REPORT), M1.SUB_WRITE, UInt8((blk >> 8) & 0xFF), UInt8(blk & 0xFF)] + chunk); pace()
        _ = try? getReport(M1.REPORT_ACK, 8); pace()
    }

    func write(_ image: [UInt8], progress: ((Double) -> Void)? = nil) throws {
        _ = try? getReport(M1.REPORT_STATUS, 8); pace()
        let probe: [UInt8] = [0xDE, 0xAD, 0xBE, 0xEF]
        try setReport(M1.REPORT, [UInt8(M1.REPORT), M1.SUB_WRITE, 0, 0] + probe + [UInt8](repeating: 0, count: M1.WRITE_CHUNK - 4)); pace()
        _ = try? getReport(M1.REPORT_ACK, 8); pace()
        guard Array(try readBlock(0)[1..<4]) == Array(probe[1...]) else { throw CardError.writeProtected }
        for blk in 0..<nWriteBlocks {
            try writeBlock(blk, image)
            if blk % 16 == 0 { progress?(Double(blk) / Double(nWriteBlocks)) }
        }
    }

    func writeAndVerify(_ image: [UInt8], progress: ((Double) -> Void)? = nil) throws {
        var lastDiff = 0, lastFirst = -1
        for attempt in 0..<3 {
            try write(image) { progress?((Double(attempt) + $0 * 0.5) / 3.0) }
            let back = try read { progress?((Double(attempt) + 0.5 + $0 * 0.5) / 3.0) }
            var diff = 0, first = -1
            for i in 0..<M1.CARD_SIZE where back[i] != image[i] { diff += 1; if first < 0 { first = i } }
            if diff == 0 { progress?(1.0); return }
            lastDiff = diff; lastFirst = first
        }
        throw CardError.verify(lastDiff, lastFirst)
    }
}

func runCLI(_ args: [String]) -> Int32 {
    let io = CardIO()
    defer { io.disconnect() }
    do {
        switch args.first {
        case "dump":
            try io.connect()
            let img = try io.read { _ in }
            try Data(img).write(to: URL(fileURLWithPath: args[1]))
            FileHandle.standardError.write("dumped \(img.count) bytes, header \(img.prefix(5).map{String(format:"%02x",$0)}.joined(separator:" "))\n".data(using:.utf8)!)
        case "write":
            let urls = Array(args.dropFirst()).map { URL(fileURLWithPath: $0) }
            let img = args[1].hasSuffix(".rom") ? [UInt8](try Data(contentsOf: urls[0])) : try buildCard(urls)
            try io.connect()
            try io.writeAndVerify(img) { p in FileHandle.standardError.write("\r\(Int(p*100))%".data(using:.utf8)!) }
            FileHandle.standardError.write("\nVERIFIED OK\n".data(using:.utf8)!)
        case "convert":
            let img = try buildCard([URL(fileURLWithPath: args[1])])
            try Data(img).write(to: URL(fileURLWithPath: args[2]))
            FileHandle.standardError.write("wrote \(img.count) bytes\n".data(using:.utf8)!)
        case "names":
            try io.connect()
            let img = try io.read { _ in }
            let (p, c) = cardPresetNames(img)
            print("CARD: KORG byte4=0x\(String(format:"%02x",img[4])) (\(img[4]==0x11 ? "RAM":"ROM") card)")
            print("PROGRAMS:"); for (i,n) in p.enumerated() { print(String(format:"  P%02d %@", i, n)) }
            print("COMBIS:");   for (i,n) in c.enumerated() { print(String(format:"  C%02d %@", i, n)) }
        default:
            FileHandle.standardError.write("usage: dump <out> | names | write <syx...|rom> | convert <syx> <out>\n".data(using:.utf8)!); return 2
        }
        return 0
    } catch {
        FileHandle.standardError.write("ERROR: \(error.localizedDescription)\n".data(using:.utf8)!); return 1
    }
}

@MainActor final class Store: ObservableObject {
    @Published var connected = false
    @Published var busy = false
    @Published var progress = 0.0
    @Published var log = ""
    private var timer: Timer?
    func startPolling() {
        connected = CardIO.cardPresent()
        timer = Timer.scheduledTimer(withTimeInterval: 2.0, repeats: true) { [weak self] _ in
            let c = CardIO.cardPresent()
            Task { @MainActor in self?.connected = c }
        }
    }
    func addLog(_ s: String) { log += s + "\n" }

    @Published var ejectOK = false
    func eject() {
        if busy { addLog("⏳ An operation is running — wait for it to finish before removing the card."); return }
        addLog("✅ Idle and safe to remove — you can unplug the card now.")
        ejectOK = true
    }

    private func usbJob(_ start: String, _ body: @escaping @Sendable (CardIO, @escaping (Double)->Void) throws -> Void,
                        done: @escaping @MainActor (Bool)->Void = {_ in}) {
        guard !busy else { return }
        busy = true; progress = 0; addLog(start)
        Task.detached {
            let io = CardIO()
            do {
                try io.connect()
                try body(io) { p in Task { @MainActor in self.progress = p } }
                io.disconnect()
                await MainActor.run { self.busy = false; done(true) }
            } catch {
                io.disconnect()
                await MainActor.run { self.addLog("❌ " + error.localizedDescription); self.busy = false; done(false) }
            }
        }
    }

    @Published var writeFiles: [URL] = []
    func writeBank() {
        guard !writeFiles.isEmpty else { addLog("Pick a .SYX file first."); return }
        let urls = writeFiles
        let imgResult = Result { urls.count == 1 && urls[0].pathExtension.lowercased() == "rom"
            ? [UInt8](try Data(contentsOf: urls[0])) : try buildCard(urls) }
        guard case .success(let img) = imgResult else {
            if case .failure(let e) = imgResult { addLog("❌ " + e.localizedDescription) }; return
        }
        usbJob("Writing \(urls.count) file(s) + verifying…", { io, prog in try io.writeAndVerify(img, progress: prog) }) { ok in
            if ok { self.addLog("✅ Written and verified. Put the card in your M1.") }
        }
    }

    @Published var cardHeader = ""
    @Published var cardProgs: [String] = []
    @Published var cardCombis: [String] = []
    @Published var identifyResult = ""
    var lastImage: [UInt8] = []
    func readCardInfo() {
        usbJob("Reading card…", { io, prog in
            let img = try io.read(progress: prog)
            let isKorg = Array(img.prefix(4)) == [0x4B,0x4F,0x52,0x47]
            let (p, c) = cardPresetNames(img)
            let realProgs = p.filter { !$0.isEmpty && $0 != "INIT" }
            let title: String
            if !isKorg { title = "Card reads blank / unwritten (no data)" }
            else {
                let kind = img[4]==0x11 ? "RAM" : "ROM"
                let first = realProgs.prefix(3).joined(separator: ", ")
                title = "Korg M1 \(kind) card · \(realProgs.count) programs" + (first.isEmpty ? "" : " · e.g. \(first)…")
            }
            Task { @MainActor in self.cardHeader = title; self.cardProgs = isKorg ? p : []; self.cardCombis = isKorg ? c : []; self.lastImage = img; self.identifyResult = "" }
        }) { ok in if ok { self.addLog(self.cardHeader) } }
    }

    func identifyCard(folder: URL) {
        guard lastImage.count == M1.CARD_SIZE, Array(lastImage.prefix(4)) == [0x4B,0x4F,0x52,0x47] else {
            addLog("Read a card first."); return
        }
        let cardProg = Array(lastImage[M1.PROG_OFF..<(M1.PROG_OFF+M1.PROG_LEN)])
        var match: String? = nil
        if let en = FileManager.default.enumerator(at: folder, includingPropertiesForKeys: nil) {
            for case let f as URL in en where f.pathExtension.lowercased() == "syx" {
                if let raw = try? Data(contentsOf: f) {
                    let b = parseSyx([UInt8](raw))
                    if let p = b[M1.F_PROG], p == cardProg {
                        match = f.deletingPathExtension().lastPathComponent
                        let brand = f.deletingLastPathComponent().lastPathComponent
                        match = "\(brand) / \(match!)"
                        break
                    }
                }
            }
        }
        identifyResult = match.map { "🔎 This card is: \($0)" } ?? "🔎 Not found in that library."
        addLog(identifyResult)
    }
    func downloadCard(to url: URL) {
        usbJob("Downloading card…", { io, prog in
            let img = try io.read(progress: prog)
            try Data(img).write(to: url)
        }) { ok in if ok { self.addLog("Saved card image → \(url.lastPathComponent)") } }
    }

    @Published var banks: [Bank] = []
    @Published var selected: Bank?
    @Published var buildProgNames: [String] = []
    @Published var buildCombiNames: [String] = []
    @Published var buildWarnings: [String] = []
    let builder = Builder()
    func loadFolder(_ dir: URL) {
        var found: [Bank] = []
        if let items = try? FileManager.default.contentsOfDirectory(at: dir, includingPropertiesForKeys: nil) {
            for u in items.sorted(by: { $0.lastPathComponent < $1.lastPathComponent })
            where u.pathExtension.lowercased() == "syx" {
                if let b = try? Bank(u) { found.append(b) }
            }
        }
        banks = found; selected = found.first
        addLog("Loaded \(found.count) bank(s) from \(dir.lastPathComponent).")
    }
    private func refreshBuild() {
        buildProgNames = builder.progs.map { recName($0[0..<10]) }
        buildCombiNames = builder.combis.map { recName($0[0..<10]) }
        buildWarnings = builder.warnings
    }
    func pickProgram(_ i: Int) { if let b = selected { builder.addProgram(b, i); refreshBuild() } }
    func pickCombi(_ i: Int)   { if let b = selected { builder.addCombi(b, i);   refreshBuild() } }
    func resetBuild() { builder.reset(); refreshBuild() }
    func writeBuild() {
        guard builder.progCount > 0 || builder.combiCount > 0 else { addLog("Add some presets first."); return }
        let img = builder.image()
        usbJob("Writing custom card (\(builder.progCount) prog, \(builder.combiCount) combi) + verifying…",
               { io, prog in try io.writeAndVerify(img, progress: prog) }) { ok in
            if ok { self.addLog("✅ Custom card written and verified.") }
        }
    }
    func saveBuild(to url: URL) {
        do { try Data(builder.image()).write(to: url); addLog("Saved custom image → \(url.lastPathComponent)") }
        catch { addLog("❌ " + error.localizedDescription) }
    }
}

struct WriteTab: View {
    @ObservedObject var s: Store
    @State private var importing = false
    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text("Drop a Korg M1 .SYX bank (or the 3 split All-Programs / All-Combis / Global files, which merge). Then Write.")
                .font(.callout).foregroundStyle(.secondary)
            ZStack {
                RoundedRectangle(cornerRadius: 10).strokeBorder(style: StrokeStyle(lineWidth: 1.5, dash: [6])).foregroundStyle(.secondary)
                if s.writeFiles.isEmpty { Text("Drop .SYX here · or Choose").foregroundStyle(.secondary) }
                else { VStack(alignment: .leading) { ForEach(s.writeFiles, id: \.self) { Text($0.lastPathComponent).font(.caption) } }.padding(8) }
            }
            .frame(height: 80)
            .onDrop(of: [.fileURL], isTargeted: nil) { ps in
                for p in ps { _ = p.loadObject(ofClass: URL.self) { u,_ in if let u { Task { @MainActor in s.writeFiles.append(u) } } } }; return true
            }
            HStack {
                Button("Choose…") { importing = true }
                Button("Clear") { s.writeFiles.removeAll() }.disabled(s.writeFiles.isEmpty)
                Spacer()
                Button { s.writeBank() } label: { Text("Write to card").bold() }
                    .keyboardShortcut(.defaultAction).disabled(s.busy || s.writeFiles.isEmpty || !s.connected)
            }
        }
        .fileImporter(isPresented: $importing, allowedContentTypes: [.data], allowsMultipleSelection: true) { r in
            if case .success(let u) = r { s.writeFiles.append(contentsOf: u) }
        }
    }
}

struct CardTab: View {
    @ObservedObject var s: Store
    @State private var saving = false
    @State private var identifying = false
    var body: some View {
        VStack(alignment: .leading, spacing: 10) {
            HStack {
                Button("Read card") { s.readCardInfo() }.disabled(s.busy || !s.connected)
                Button("Identify from library…") { identifying = true }.disabled(s.busy || s.lastImage.isEmpty)
                Button("Download…") { saving = true }.disabled(s.busy || !s.connected)
                Spacer()
            }
            Text(s.cardHeader.isEmpty ? "Click “Read card” to see what’s on it." : s.cardHeader)
                .font(.callout).bold().foregroundStyle(s.cardHeader.contains("blank") ? .orange : .primary)
            if !s.identifyResult.isEmpty {
                Text(s.identifyResult).font(.callout).foregroundStyle(.tint)
            }
            HStack(alignment: .top, spacing: 12) {
                listCol("Programs (sounds)", s.cardProgs)
                listCol("Combinations", s.cardCombis)
            }
        }
        .fileExporter(isPresented: $saving, document: RomDoc(), contentType: .data, defaultFilename: "card-backup.rom") { r in
            if case .success(let u) = r { s.downloadCard(to: u) }
        }
        .fileImporter(isPresented: $identifying, allowedContentTypes: [.folder]) { r in
            if case .success(let u) = r { _ = u.startAccessingSecurityScopedResource(); s.identifyCard(folder: u) }
        }
    }
    func listCol(_ title: String, _ items: [String]) -> some View {
        VStack(alignment: .leading, spacing: 4) {
            Text(title).font(.caption).bold()
            ScrollView { LazyVStack(alignment: .leading, spacing: 1) {
                if items.isEmpty { Text("—").foregroundStyle(.secondary).font(.caption) }
                ForEach(Array(items.enumerated()), id: \.offset) { i, n in
                    Text(String(format: "%02d  %@", i, n.isEmpty ? "·" : n)).font(.system(.caption, design: .monospaced))
                        .frame(maxWidth: .infinity, alignment: .leading)
                } }.padding(6) }
            .frame(maxWidth: .infinity, maxHeight: .infinity)
            .background(Color(nsColor: .textBackgroundColor)).clipShape(RoundedRectangle(cornerRadius: 6))
        }.frame(maxHeight: .infinity)
    }
}

struct BuildTab: View {
    @ObservedObject var s: Store
    @State private var choosingFolder = false
    @State private var saving = false
    @State private var dropTargeted = false

    func handleDrop(_ providers: [NSItemProvider]) -> Bool {
        for p in providers {
            _ = p.loadObject(ofClass: NSString.self) { obj, _ in
                guard let str = obj as? String, let idx = Int(str.dropFirst()) else { return }
                Task { @MainActor in
                    if str.hasPrefix("P") { s.pickProgram(idx) } else if str.hasPrefix("C") { s.pickCombi(idx) }
                }
            }
        }
        return true
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            HStack {
                Button("Choose backups folder…") { choosingFolder = true }
                Spacer()
                Text("Card build: \(s.buildProgNames.count)/100 programs · \(s.buildCombiNames.count)/100 combis")
                    .font(.caption).foregroundStyle(.secondary)
            }
            HStack(alignment: .top, spacing: 10) {
                VStack(alignment: .leading, spacing: 4) {
                    Text("Backups (\(s.banks.count))").font(.caption).bold()
                    ScrollView { LazyVStack(alignment: .leading, spacing: 1) {
                        ForEach(s.banks, id: \.url) { b in
                            Text(b.title).font(.caption).lineLimit(1)
                                .padding(.vertical,3).padding(.horizontal,5).frame(maxWidth: .infinity, alignment: .leading)
                                .background(s.selected?.url == b.url ? Color.accentColor.opacity(0.3) : .clear)
                                .clipShape(RoundedRectangle(cornerRadius:4))
                                .contentShape(Rectangle()).onTapGesture { s.selected = b }
                        } }.padding(4) }
                    .frame(width: 150).frame(maxHeight: .infinity)
                    .background(Color(nsColor:.textBackgroundColor)).clipShape(RoundedRectangle(cornerRadius:6))
                }
                VStack(alignment: .leading, spacing: 4) {
                    Text(s.selected.map { "Presets in “\($0.title)” — drag → or click +" } ?? "Select a backup").font(.caption).bold()
                    HStack(alignment: .top, spacing: 6) {
                        presetCol("Programs", count: 100, tag: "P", name: { s.selected?.progName($0) ?? "" }, add: { s.pickProgram($0) })
                        presetCol("Combinations (pulls its programs)", count: 100, tag: "C", name: { s.selected?.combiName($0) ?? "" }, add: { s.pickCombi($0) })
                    }
                }.frame(maxWidth: .infinity)
                VStack(alignment: .leading, spacing: 4) {
                    Text("Card build ▾ drop here").font(.caption).bold()
                    ScrollView { LazyVStack(alignment: .leading, spacing: 1) {
                        if s.buildProgNames.isEmpty && s.buildCombiNames.isEmpty {
                            Text("Drag presets here\n(or click +)").font(.caption).foregroundStyle(.secondary).padding(.top,8)
                        }
                        ForEach(Array(s.buildCombiNames.enumerated()), id: \.offset) { _, n in
                            Text("🎹 " + n).font(.system(.caption2, design:.monospaced)) }
                        ForEach(Array(s.buildProgNames.enumerated()), id: \.offset) { _, n in
                            Text("• " + n).font(.system(.caption2, design:.monospaced)) }
                    }.padding(6) }
                    .frame(width: 170).frame(maxHeight: .infinity)
                    .background(dropTargeted ? Color.accentColor.opacity(0.25) : Color(nsColor:.textBackgroundColor))
                    .clipShape(RoundedRectangle(cornerRadius:6))
                    .overlay(RoundedRectangle(cornerRadius:6).strokeBorder(dropTargeted ? Color.accentColor : .clear, lineWidth:2))
                    .onDrop(of: [.text], isTargeted: $dropTargeted) { handleDrop($0) }
                    HStack { Button("Clear") { s.resetBuild() }; Button("Save…") { saving = true } }
                }
            }
            if !s.buildWarnings.isEmpty { Text(s.buildWarnings.joined(separator: " · ")).font(.caption2).foregroundStyle(.orange) }
            HStack {
                Spacer()
                Button { s.writeBuild() } label: { Text("Write custom card").bold() }
                    .keyboardShortcut(.defaultAction).disabled(s.busy || !s.connected || (s.buildProgNames.isEmpty && s.buildCombiNames.isEmpty))
            }
        }
        .fileImporter(isPresented: $choosingFolder, allowedContentTypes: [.folder]) { r in
            if case .success(let u) = r { _ = u.startAccessingSecurityScopedResource(); s.loadFolder(u) }
        }
        .fileExporter(isPresented: $saving, document: RomDoc(), contentType: .data, defaultFilename: "custom-card.rom") { r in
            if case .success(let u) = r { s.saveBuild(to: u) }
        }
    }
    func presetCol(_ title: String, count: Int, tag: String, name: @escaping (Int)->String, add: @escaping (Int)->Void) -> some View {
        VStack(alignment: .leading, spacing: 3) {
            Text(title).font(.caption2).foregroundStyle(.secondary).lineLimit(1)
            ScrollView { LazyVStack(alignment: .leading, spacing: 1) {
                ForEach(0..<count, id: \.self) { i in
                    let nm = name(i)
                    if !nm.isEmpty {
                        HStack(spacing: 6) {
                            Text(String(format:"%02d %@", i, nm)).font(.system(.caption2, design:.monospaced)).lineLimit(1)
                            Spacer()
                            Button { add(i) } label: {
                                Image(systemName: "plus.circle.fill").font(.body).foregroundStyle(.tint)
                            }.buttonStyle(.plain)
                        }
                        .padding(.vertical,2).padding(.horizontal,5)
                        .contentShape(Rectangle())
                        .onDrag { NSItemProvider(object: "\(tag)\(i)" as NSString) }
                    }
                } }.padding(4) }
            .frame(maxWidth: .infinity, maxHeight: .infinity)
            .background(Color(nsColor:.textBackgroundColor)).clipShape(RoundedRectangle(cornerRadius:6))
        }
    }
}

struct RomDoc: FileDocument {
    static var readableContentTypes: [UTType] { [.data] }
    init() {}
    init(configuration: ReadConfiguration) throws {}
    func fileWrapper(configuration: WriteConfiguration) throws -> FileWrapper { FileWrapper(regularFileWithContents: Data()) }
}

struct ContentView: View {
    @StateObject var s = Store()
    var body: some View {
        VStack(spacing: 10) {
            HStack {
                Text("M1 RAM Writer").font(.title2).bold()
                Spacer()
                Circle().fill(s.connected ? .green : .gray).frame(width: 10, height: 10)
                Text(s.connected ? "card connected" : "no card").font(.caption).foregroundStyle(.secondary)
                Button("Eject") { s.eject() }.disabled(!s.connected || s.busy).help("Confirm it's safe to unplug the card")
            }
            TabView {
                WriteTab(s: s).padding(12).tabItem { Text("Write bank") }
                BuildTab(s: s).padding(12).tabItem { Text("Build custom") }
                CardTab(s: s).padding(12).tabItem { Text("Card") }
            }
            if s.busy { ProgressView(value: s.progress) }
            ScrollViewReader { _ in
                ScrollView { Text(s.log).font(.system(.caption2, design: .monospaced)).frame(maxWidth: .infinity, alignment: .leading).textSelection(.enabled) }
                    .frame(height: 90).background(Color(nsColor:.textBackgroundColor)).clipShape(RoundedRectangle(cornerRadius:6))
            }
        }
        .padding(14).frame(minWidth: 780, idealWidth: 900, minHeight: 580, idealHeight: 640)
        .onAppear { s.startPolling() }
        .alert("Safe to remove", isPresented: $s.ejectOK) { Button("OK") {} }
            message: { Text("No operations are running. You can unplug the card now.") }
    }
}

struct M1RamWriterApp: App {
    var body: some Scene { WindowGroup("M1 RAM Writer") { ContentView() }.windowResizability(.contentMinSize) }
}

let cliArgs = Array(CommandLine.arguments.dropFirst())
if let first = cliArgs.first, ["dump","names","write","convert"].contains(first) {
    exit(runCLI(cliArgs))
} else {
    M1RamWriterApp.main()
}
