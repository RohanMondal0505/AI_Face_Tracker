"use client";

import { useEffect, useRef, useState } from "react";

const empty = { blink_count: 0, eye_status: "—", head_status: "—", calibration_progress: 0, face_detected: false };

export default function Home() {
	const video = useRef(null);
	const overlay = useRef(null);
	const session = useRef(null);
	const [status, setStatus] = useState("idle");
	const [error, setError] = useState("");
  const [result, setResult] = useState(empty);

	function dispose(current) {
		if (!current) return;
		current.cancelled = true;
		clearTimeout(current.timer);
		clearTimeout(current.watchdog);
		current.stream?.getTracks().forEach((track) => track.stop());
		current.socket?.close();
		if (session.current === current) {
			session.current = null;
			if (video.current) video.current.srcObject = null;
			const canvas = overlay.current;
			canvas?.getContext("2d").clearRect(0, 0, canvas.width, canvas.height);
		}
	}

	useEffect(() => () => dispose(session.current), []);

	function stop() {
		dispose(session.current);
		setStatus("idle");
		setResult(empty);
	}

	async function start() {
		dispose(session.current);
		const current = { cancelled: false };
		session.current = current;
		setError("");
		setResult(empty);
		setStatus("connecting");
		function fail(message) {
			if (current.cancelled) return;
			dispose(current);
			setError(message);
			setStatus("idle");
		}
		function armTimeout() {
			clearTimeout(current.watchdog);
			current.watchdog = setTimeout(() => fail("The tracker stopped responding. Check the backend and try again."), 15000);
		}
		try {
			if (!navigator.mediaDevices?.getUserMedia) throw new Error("Camera access requires localhost or HTTPS.");
			const stream = await navigator.mediaDevices.getUserMedia({
				video: { width: { ideal: 640 }, height: { ideal: 480 }, facingMode: "user" },
				audio: false,
			});
			if (current.cancelled) {
				stream.getTracks().forEach((track) => track.stop());
				return;
			}
			current.stream = stream;
			stream.getVideoTracks()[0].onended = () => fail("Camera access ended. Start tracking to reconnect.");
			video.current.srcObject = stream;
			await video.current.play();
			if (current.cancelled) return;

			const endpoint =
				process.env.NEXT_PUBLIC_TRACKER_WS_URL ||
				`${location.protocol === "https:" ? "wss" : "ws"}://${location.hostname}:8000/ws/track`;
			const socket = new WebSocket(endpoint);
			current.socket = socket;
			armTimeout();
			const capture = document.createElement("canvas");

			function sendFrame() {
				if (current.cancelled || socket.readyState !== WebSocket.OPEN) return;
				const source = video.current;
				if (!source?.videoWidth) {
					current.timer = setTimeout(sendFrame, 100);
					return;
				}
				capture.width = Math.min(source.videoWidth, 640);
				capture.height = Math.round((source.videoHeight * capture.width) / source.videoWidth);
				capture.getContext("2d").drawImage(source, 0, 0, capture.width, capture.height);
				capture.toBlob(
					(blob) => {
						if (current.cancelled || socket.readyState !== WebSocket.OPEN) return;
						if (!blob) {
							fail("Could not capture a camera frame.");
							return;
						}
						socket.send(blob);
						armTimeout();
					},
					"image/jpeg",
					0.8,
				);
			}

			socket.onmessage = (event) => {
				if (current.cancelled) return;
				let data;
				try {
					data = JSON.parse(event.data);
				} catch {
					fail("Invalid response from the tracker.");
					return;
				}
				if (data.type === "error") {
					fail(data.message);
					return;
				}
				if (data.type === "reset") {
					setResult(empty);
					return;
				}
				clearTimeout(current.watchdog);
				if (data.type === "ready") {
					setStatus("tracking");
					sendFrame();
					return;
				}
				if (data.type !== "result") return;
				setResult(data);
				const canvas = overlay.current;
				canvas.width = capture.width;
				canvas.height = capture.height;
				const ctx = canvas.getContext("2d");
				ctx.clearRect(0, 0, canvas.width, canvas.height);
				data.landmarks.forEach((point, index) => {
					ctx.fillStyle = [1, 33, 263].includes(index) ? "#ffffff" : "#6de9bf";
					ctx.beginPath();
					ctx.arc(
						point.x * canvas.width,
						point.y * canvas.height,
						[1, 33, 263].includes(index) ? 3 : 1.25,
						0,
						Math.PI * 2,
					);
					ctx.fill();
				});
				// Wait for each result before sending another frame: no growing queue.
				current.timer = setTimeout(sendFrame, 30);
			};
			socket.onerror = () => fail("Cannot connect to the tracker. Make sure the Python backend is running on port 8000.");
			socket.onclose = () => fail("Backend disconnected. Start tracking to reconnect.");
		} catch (err) {
			fail(
				err.name === "NotAllowedError"
					? "Camera permission was denied. Allow camera access in your browser, then try again."
					: err.message || "Unable to start the camera.",
			);
		}
	}

	function reset() {
		if (session.current?.socket?.readyState === WebSocket.OPEN) {
			session.current.socket.send(JSON.stringify({ type: "reset" }));
		}
	}

	const active = status === "tracking";
	return (
		<main>
			<header>
				<a className="brand" href="/">
					<span className="brand-mark" aria-hidden="true">⌖</span> <span>FACE<span className="brand-accent"> / </span>TRACKER</span>
				</a>
				<span className="tag"><i /> VISION INTERFACE <span className="version">/ 01</span></span>
			</header>
			<section className="intro">
				<p className="eyebrow">HUMAN MOVEMENT. DIGITALLY DECODED.</p>
				<h1>
					Beyond the surface.
					<br />
					<span>Every motion, mapped.</span>
				</h1>
				<p>Track facial landmarks, eye blinks, and head movement from your webcam.</p>
			</section>
			<section className="workspace" aria-label="Face tracking workspace">
				<div className={`camera-card ${active ? "is-active" : ""}`}>
					<div className="card-heading">
						<span>01 / OPTICAL FEED</span>
						<span className={`status ${active ? "live" : ""}`}>
							<i />
							{active ? "LIVE" : status === "connecting" ? "CONNECTING" : "STANDBY"}
						</span>
					</div>
					<div className="viewport">
						<video ref={video} autoPlay muted playsInline />
                        <div className="hud-corners" aria-hidden="true"><b /><b /><b /><b /></div>
						<canvas ref={overlay} aria-hidden="true" />
						{status === "idle" && (
							<div className="placeholder">
								<div className="scanner" aria-hidden="true">
                                    <div className="scanner-orbit" />
                                    <svg viewBox="0 0 160 180" className="face-wireframe" fill="none">
                                        <path d="M80 15 45 28 29 64 35 112 54 148 80 165 106 148 125 112 131 64 115 28Z M45 28 80 48 115 28 M29 64 58 63 80 48 102 63 131 64 M35 112 59 99 80 110 101 99 125 112 M54 148 61 126 80 135 99 126 106 148 M80 48V85L68 108 80 114 92 108 80 85 M42 77 58 70 70 78 58 83Z M90 78 102 70 118 77 102 83Z M61 126 80 121 99 126 80 135Z M58 83 59 99 61 126 M102 83 101 99 99 126 M80 135V165" />
                                        {[ [80,15], [45,28], [115,28], [29,64], [131,64], [80,48], [58,70], [102,70], [59,99], [101,99], [80,114], [61,126], [99,126], [80,165] ].map(([x,y]) => <circle key={`${x}-${y}`} cx={x} cy={y} r="2.5" />)}
                                    </svg>
                                    <div className="scan-beam" />
                                </div>
								<h2>Awaiting visual input.</h2>
								<p>Initialize your camera to begin real-time tracking.</p>
							</div>
						)}
						{status === "connecting" && <div className="feed-label" role="status">INITIALIZING CAMERA CONNECTION…</div>}
                        {active && (
							<div className="feed-label">{result.face_detected ? "FACE DETECTED" : "LOOK TOWARD YOUR CAMERA"}</div>
						)}
					</div>
					<div className="controls">
						<button className="primary" onClick={status === "idle" ? start : stop}>
							{status === "idle" ? "Initialize tracking ↗" : status === "connecting" ? "Cancel" : "Stop tracking"}
						</button>
						<button className="secondary" onClick={reset} disabled={!active}>
							Reset session
						</button>
					</div>
				</div>
				<aside>
					<div className="readings-heading">
						<span>02 / TELEMETRY</span>
						<span>↗</span>
					</div>
					<div className="metric blink-metric">
						<span>Blink count <span className="metric-code">BLK / 01</span></span>
						<strong className="count">{String(result.blink_count).padStart(2, "0")}</strong>
						<small>Completed eye blinks this session</small>
					</div>
					<div className="metric compact">
						<span>Eye status <span className="metric-code">EYE / 02</span></span>
						<strong>{result.eye_status}</strong>
					</div>
					<div className="metric compact">
						<span>Head position <span className="metric-code">POS / 03</span></span>
						<strong>{result.head_status}</strong>
					</div>
					<div className="calibration">
						<div>
							<span>BASELINE CALIBRATION</span>
							<span>{Math.round(result.calibration_progress * 100)}%</span>
						</div>
						<progress aria-label="Baseline calibration" value={result.calibration_progress} max="1" />
						<p>
							{result.calibration_progress === 1
								? "Ready. Move your head to explore."
								: "Hold your head still while the first 30 face frames establish your center."}
						</p>
					</div>
				</aside>
			</section>
			{error && (
				<p className="error" role="alert">
					{error}
				</p>
			)}
			<footer>
				<span>
					<i /> Frames are processed by your connected Python backend.
				</span>
				<span>FACE TRACKER <span className="footer-divider">/</span> VISION LAB</span>
			</footer>
		</main>
	);
}
