// Passes raw microphone samples to the page, untouched (no compression, no gain, no filtering).
class RecorderProcessor extends AudioWorkletProcessor {
  process(inputs) {
    const ch = inputs[0] && inputs[0][0];
    if (ch && ch.length) this.port.postMessage(ch.slice(0));
    return true;
  }
}
registerProcessor("recorder", RecorderProcessor);
