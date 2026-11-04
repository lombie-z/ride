// What this Mac's WebKit (Safari's engine) really decodes with Web Audio, and how many frames it gets back. Encoders add
// padding, and that padding is what makes a "seamless" loop tick, so the frame count matters as much as whether it plays.
//
//   swiftc -O webkit_decode_test.swift -o /tmp/somewhere/wk && /tmp/somewhere/wk file1.ogg file2.m4a ...
//
// Prints JSON: for each file, decoded or the error, frames, rate, and where the loudest sample falls (put a click in the
// source at a known frame to read off how far the codec shifted it). It runs WKWebView without showing a window. It tests
// macOS WebKit only; iOS needs its own check on a device.
import Foundation
import WebKit

final class Runner: NSObject, WKNavigationDelegate {
    let web: WKWebView
    let files: [String]
    init(files: [String]) {
        self.files = files
        web = WKWebView(frame: .zero, configuration: WKWebViewConfiguration())
        super.init()
        web.navigationDelegate = self
        web.loadHTMLString("<!doctype html><title>t</title>", baseURL: URL(string: "https://example.invalid/"))
    }

    func webView(_ webView: WKWebView, didFinish navigation: WKNavigation!) {
        Task { @MainActor in
            var results: [[String: Any]] = []
            for path in files {
                let data = (try? Data(contentsOf: URL(fileURLWithPath: path))) ?? Data()
                let js = """
                const bin = Uint8Array.from(atob(b64), c => c.charCodeAt(0));
                const ctx = new OfflineAudioContext(2, 1, 48000);
                try {
                  const buf = await ctx.decodeAudioData(bin.buffer);
                  const ch = buf.getChannelData(0);
                  let max = 0, at = -1;
                  for (let i = 0; i < ch.length; i++) { const v = Math.abs(ch[i]); if (v > max) { max = v; at = i; } }
                  return JSON.stringify({ ok: true, frames: buf.length, rate: buf.sampleRate, channels: buf.numberOfChannels, loudestAt: at, loudest: max });
                } catch (e) { return JSON.stringify({ ok: false, error: String(e) }); }
                """
                do {
                    let r = try await webView.callAsyncJavaScript(js, arguments: ["b64": data.base64EncodedString()], contentWorld: .page)
                    var o = (try? JSONSerialization.jsonObject(with: Data((r as? String ?? "{}").utf8))) as? [String: Any] ?? [:]
                    o["file"] = (path as NSString).lastPathComponent
                    results.append(o)
                } catch {
                    results.append(["file": (path as NSString).lastPathComponent, "ok": false, "error": "\(error)"])
                }
            }
            webView.evaluateJavaScript("navigator.userAgent") { ua, _ in
                let out: [String: Any] = ["userAgent": ua ?? "", "results": results]
                let json = try! JSONSerialization.data(withJSONObject: out, options: [.prettyPrinted, .sortedKeys])
                print(String(data: json, encoding: .utf8)!)
                exit(0)
            }
        }
    }
}

let files = Array(CommandLine.arguments.dropFirst())
if files.isEmpty { print("usage: swift webkit_decode_test.swift file..."); exit(2) }
let app = NSApplication.shared
app.setActivationPolicy(.prohibited)
let runner = Runner(files: files)
DispatchQueue.main.asyncAfter(deadline: .now() + 60) { print("timed out"); exit(1) }
app.run()
