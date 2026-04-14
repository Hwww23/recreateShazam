import { useState, useRef, useEffect } from "react"
import { Mic, MicOff, Upload, Music, Loader } from "lucide-react"
import "./App.css"

const API = import.meta.env.VITE_API_URL || "http://localhost:8000"

export default function App() {
  const [state, setState] = useState("idle")
  // states: idle | recording | loading | result | error

  const [result, setResult]   = useState(null)
  const [error, setError]     = useState("")
  const [status, setStatus]   = useState("")
  const [songs, setSongs]     = useState([])
  const [ingesting, setIngesting] = useState(false)

  const mediaRecorderRef = useRef(null)
  const chunksRef        = useRef([])

  // Load song library on startup
  useEffect(() => {
    fetchSongs()
  }, [])

  async function fetchSongs() {
    try {
      const res = await fetch(`${API}/songs`)
      const data = await res.json()
      setSongs(data)
    } catch {
      console.error("Could not fetch songs")
    }
  }

  // ── Recording ──────────────────────────────

  async function startRecording() {
    setResult(null)
    setError("")
    chunksRef.current = []

    try {
      // Ask browser for microphone access
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
      const recorder = new MediaRecorder(stream)
      mediaRecorderRef.current = recorder

      // Each time data is available, push it to our chunks array
      recorder.ondataavailable = (e) => {
        if (e.data.size > 0) chunksRef.current.push(e.data)
      }

      // When recording stops, send the audio to the backend
      recorder.onstop = async () => {
        const blob = new Blob(chunksRef.current, { type: "audio/webm" })
        await recognize(blob, "recording.webm")
        // Stop all microphone tracks to release the mic
        stream.getTracks().forEach(t => t.stop())
      }

      recorder.start()
      setState("recording")
      setStatus("Listening... tap again to identify")

      // Auto-stop after 10 seconds
      setTimeout(() => {
        if (recorder.state === "recording") stopRecording()
      }, 10000)

    } catch {
      setError("Microphone access denied. Please allow mic access and try again.")
      setState("idle")
    }
  }

  async function startSystemAudio() {
    console.log("startSystemAudio called")
    setResult(null)
    setError("")
    chunksRef.current = []

    try {
      // Ask browser to capture system/tab audio
      // The user will see a browser popup asking what to share
      console.log("calling getDisplayMedia...")
      const stream = await navigator.mediaDevices.getDisplayMedia({
        video: true,   // Chrome requires video:true to show the popup
        audio: true
      })
      // immediately stop the video track — we only want audio
      stream.getVideoTracks().forEach(t => t.stop())
      console.log("got stream:", stream)

      const recorder = new MediaRecorder(stream)
      mediaRecorderRef.current = recorder

      recorder.ondataavailable = (e) => {
        if (e.data.size > 0) chunksRef.current.push(e.data)
      }

      recorder.onstop = async () => {
        const blob = new Blob(chunksRef.current, { type: "audio/webm" })
        await recognize(blob, "system_audio.webm")
        stream.getTracks().forEach(t => t.stop())
      }

      recorder.start()
      setState("recording")
      setStatus("Capturing system audio... tap again to identify")

      setTimeout(() => {
        if (recorder.state === "recording") stopRecording()
      }, 10000)

    } catch {
      setError("System audio capture was cancelled or not supported.")
      setState("idle")
    }
  }

  function stopRecording() {
    if (mediaRecorderRef.current?.state === "recording") {
      mediaRecorderRef.current.stop()
      setState("loading")
      setStatus("Identifying...")
    }
  }

  function handleRecordBtn() {
    if (state === "idle" || state === "result" || state === "error") {
      startRecording()
    } else if (state === "recording") {
      stopRecording()
    }
  }

  // ── File upload ────────────────────────────

  async function handleFileUpload(e) {
    const file = e.target.files[0]
    if (!file) return
    setState("loading")
    setStatus("Identifying...")
    setResult(null)
    setError("")
    await recognize(file, file.name)
    // Reset the input so the same file can be uploaded again
    e.target.value = ""
  }

  // ── Recognize ──────────────────────────────

  async function recognize(blob, filename) {
    // try {
    //   const formData = new FormData()
    //   // "file" must match the parameter name in FastAPI: file: UploadFile = File(...)
    //   formData.append("file", blob, filename)

    //   const res = await fetch(`${API}/recognize`, {
    //     method: "POST",
    //     body: formData
    //   })

    //   if (res.status === 404) {
    //     setError("No match found. Try a longer clip or add more songs.")
    //     setState("error")
    //     setStatus("")
    //     return
    //   }

    //   if (!res.ok) throw new Error("Server error")

    //   const data = await res.json()
    //   setResult(data)
    //   setState("result")
    //   setStatus("")

    // } catch {
    //   setError("Something went wrong. Is the backend running?")
    //   setState("error")
    //   setStatus("")
    // }

    try {
      const formData = new FormData()
      formData.append("file", blob, filename)

      // Step 1 — submit job
      const res = await fetch(`${API}/recognize`, {
        method: "POST",
        body: formData
      })

      if (!res.ok) throw new Error("Server error")
      const { job_id } = await res.json()

      // Step 2 — poll for result
      setStatus("Identifying...")
      const result = await pollResult(job_id)

      if (!result) {
        setError("No match found. Try a longer clip or add more songs.")
        setState("error")
        setStatus("")
        return
      }

      setResult(result)
      setState("result")
      setStatus("")

    } catch (err) {
      console.error("Recognize error:", err)
      setError("Something went wrong. Is the backend running?")
      setState("error")
      setStatus("")
    }
  }

  async function pollResult(job_id) {
    console.log("Starting polling for job:", job_id)
    const MAX_ATTEMPTS = 30  // 30 seconds timeout
    const INTERVAL_MS = 1000

    for (let i = 0; i < MAX_ATTEMPTS; i++) {
      await new Promise(r => setTimeout(r, INTERVAL_MS))
      console.log(`Poll attempt ${i + 1} for ${job_id}`)

      const res = await fetch(`${API}/results/${job_id}`)
      const data = await res.json()
      console.log("Poll response:", data)

      if (data.status === "found") return data
      if (data.status === "not_found") return null
      if (data.status === "error") throw new Error(data.message)

      // Update status message based on progress
      if (data.status === "processing" && data.message) {
        setStatus(data.message)
      }
    }

    throw new Error("Timed out waiting for result")
  }

  // ── Ingest a new song ──────────────────────

  async function handleIngest(e) {
    const file = e.target.files[0]
    if (!file) return
    setIngesting(true)

    try {
      const formData = new FormData()
      formData.append("file", file, file.name)

      const res = await fetch(`${API}/songs`, {
        method: "POST",
        body: formData
      })

      if (!res.ok) throw new Error()
      const data = await res.json()
      alert(`✓ Added "${data.title}" by ${data.artist}`)
      fetchSongs()  // refresh library

    } catch {
      alert("Failed to ingest song. Check the backend terminal for errors.")
    } finally {
      setIngesting(false)
      e.target.value = ""
    }
  }

  // ── Render ─────────────────────────────────

  function renderIcon() {
    if (state === "loading")   return <Loader size={36} className="spin" />
    if (state === "recording") return <MicOff size={36} />
    return <Mic size={36} />
  }

  function renderLabel() {
    if (state === "loading")   return "Identifying..."
    if (state === "recording") return "Tap to stop"
    return "Tap to listen"
  }

  return (
    <div className="app">
      <h1>SoundMatch</h1>
      <p className="subtitle">Identify any song instantly</p>

      {/* Record button */}
      <button
        className={`record-btn ${state === "recording" ? "recording" : ""} ${state === "loading" ? "loading" : ""}`}
        onClick={handleRecordBtn}
        disabled={state === "loading"}
      >
        {renderIcon()}
        {renderLabel()}
      </button>

      {/* Upload a clip to identify */}
      <label className="upload-label">
        <Upload size={14} />
        Upload clip to identify
        <input
          type="file"
          accept="audio/*"
          onChange={handleFileUpload}
          disabled={state === "loading"}
        />
      </label>

      {/* Capture system audio */}
      <button
        className="upload-label"
        onClick={startSystemAudio}
        disabled={state === "loading"}
      >
        <Music size={14} />
        Identify what's playing
      </button>

      {/* Status message */}
      {status && <p className="status">{status}</p>}

      {/* Result */}
      {state === "result" && result && (
        <div className="result-card">
          <div className="song-title">{result.title}</div>
          <div className="song-artist">{result.artist}</div>
          <div className="result-meta">
            <span>⚡ {result.score} votes</span>
            <span>⏱ starts at {result.offset_seconds}s</span>
          </div>
        </div>
      )}

      {/* Error */}
      {state === "error" && (
        <p className="no-match">{error}</p>
      )}

      {/* Divider */}
      <div style={{ width: "100%", borderTop: "1px solid #2d2d4e" }} />

      {/* Add song to library */}
      <label>
        <button
          className="ingest-btn"
          disabled={ingesting}
          onClick={(e) => e.currentTarget.nextSibling?.click()}
        >
          {ingesting ? "Adding..." : "+ Add song to library"}
        </button>
        <input
          type="file"
          accept="audio/*"
          style={{ display: "none" }}
          onChange={handleIngest}
        />
      </label>

      {/* Song library */}
      {songs.length > 0 && (
        <div className="library">
          <h2>Library ({songs.length})</h2>
          <div className="song-list">
            {songs.map(song => (
              <div className="song-item" key={song.id}>
                <div>
                  <div className="title">{song.title}</div>
                  <div className="artist">{song.artist}</div>
                </div>
                <Music size={16} color="#444" />
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}