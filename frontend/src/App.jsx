import { useEffect, useState } from "react";
import {
  API_BASE,
  createRun,
  exportCvat,
  getDemoSources,
  getHealth,
  getRun,
  getRuns,
  getTimeline,
  uploadMedia,
} from "./api";
import { mockRun, mockSources, mockTimeline } from "./mockData";

const defaultControls = {
  confidence_threshold: 0.55,
  detection_interval: 4,
  max_track_age: 12,
  min_box_area: 900,
  process_scale: 0.8,
  alert_area_ratio: 0.025,
  motion_weight: 0.35,
  glare_suppression: 0.45,
  sharpen_strength: 0.35,
  temporal_smoothing: 0.2,
  disturbance_profile: "mixed",
  enable_clahe: true,
  enable_glare_mask: true,
  enable_temporal_smoothing: true,
  comparison_view: true,
};

function App() {
  const [sources, setSources] = useState([]);
  const [runs, setRuns] = useState([]);
  const [selectedRunId, setSelectedRunId] = useState("");
  const [selectedSourceId, setSelectedSourceId] = useState("mvtd-23-boat");
  const [controls, setControls] = useState(defaultControls);
  const [timeline, setTimeline] = useState([]);
  const [connectionMode, setConnectionMode] = useState("loading");
  const [statusMessage, setStatusMessage] = useState("Connecting to analysis backend...");
  const [inputMode, setInputMode] = useState("demo");
  const [uploadedSource, setUploadedSource] = useState(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isUploading, setIsUploading] = useState(false);
  const [isExporting, setIsExporting] = useState(false);

  const selectedRun =
    runs.find((candidate) => candidate.run_id === selectedRunId) ??
    runs[0] ??
    (connectionMode === "demo" ? mockRun : null);
  const selectedSource =
    sources.find((candidate) => candidate.id === selectedSourceId) ?? sources[0] ?? mockSources[0];
  const summary = selectedRun?.summary ?? (connectionMode === "demo" ? mockRun.summary : null);
  const alerts =
    selectedRun?.alerts?.length > 0 ? selectedRun.alerts : connectionMode === "demo" ? mockRun.alerts : [];
  const tracks =
    selectedRun?.latest_tracks?.length > 0
      ? selectedRun.latest_tracks
      : connectionMode === "demo"
        ? mockRun.latest_tracks
        : [];
  const inputSource =
    inputMode === "upload"
      ? {
          title: uploadedSource?.title ?? "Local Upload",
          description: uploadedSource
            ? `Uploaded ${formatMediaKind(uploadedSource.media_kind)} from your system for direct analysis.`
            : "Upload a local video or still image to run the pipeline without relying on a preloaded demo.",
          source_page: "",
          exists_locally: Boolean(uploadedSource?.source_path),
          license_name: uploadedSource?.converted_to_video ? "Local upload · converted to MP4" : "Local upload",
          note: "",
        }
      : {
          ...selectedSource,
          note: selectedSource?.exists_locally
            ? ""
            : "This demo source is listed in the UI but is not stored on the backend yet. Upload a local file or switch to a downloaded clip before starting analysis.",
        };
  const canStartAnalysis =
    connectionMode === "live" &&
    !isSubmitting &&
    (inputMode === "upload" ? Boolean(uploadedSource?.source_path) : Boolean(selectedSource?.exists_locally));

  useEffect(() => {
    async function bootstrap() {
      try {
        await getHealth();
        const [liveSources, liveRuns] = await Promise.all([getDemoSources(), getRuns()]);
        setSources(liveSources);
        setRuns(liveRuns);
        setSelectedSourceId(liveSources[0]?.id ?? "mvtd-23-boat");
        setSelectedRunId(liveRuns[0]?.run_id ?? "");
        setConnectionMode("live");
        setStatusMessage("Backend connected. Operator console is live.");
      } catch (error) {
        setConnectionMode("demo");
        setSources(mockSources);
        setRuns([mockRun]);
        setSelectedRunId(mockRun.run_id);
        setStatusMessage(
          "Backend is offline. The UI is running in presentation mode until FastAPI is started.",
        );
      }
    }

    bootstrap();
  }, []);

  useEffect(() => {
    if (connectionMode !== "live") {
      return;
    }
    if (!selectedRun) {
      setStatusMessage("Backend connected. Choose a downloaded clip or upload local media to begin.");
      return;
    }
    setStatusMessage(buildRunStatusMessage(selectedRun));
  }, [
    connectionMode,
    selectedRun?.error,
    selectedRun?.progress,
    selectedRun?.run_id,
    selectedRun?.status,
  ]);

  useEffect(() => {
    if (!selectedRun?.artifacts?.timeline_json) {
      setTimeline(connectionMode === "demo" ? mockTimeline : []);
      return;
    }

    let cancelled = false;
    async function loadTimeline() {
      try {
        const payload = await getTimeline(selectedRun.artifacts.timeline_json);
        if (!cancelled) {
          setTimeline(payload);
        }
      } catch (error) {
        if (!cancelled) {
          setTimeline(connectionMode === "demo" ? mockTimeline : []);
        }
      }
    }

    loadTimeline();
    return () => {
      cancelled = true;
    };
  }, [selectedRun?.artifacts?.timeline_json, connectionMode]);

  useEffect(() => {
    if (connectionMode !== "live" || !selectedRunId) {
      return undefined;
    }
    if (selectedRun?.status !== "queued" && selectedRun?.status !== "running") {
      return undefined;
    }

    const interval = window.setInterval(async () => {
      try {
        const updated = await getRun(selectedRunId);
        setRuns((currentRuns) => {
          const filtered = currentRuns.filter((item) => item.run_id !== updated.run_id);
          return [updated, ...filtered];
        });
      } catch (error) {
        setStatusMessage("Polling paused because the backend could not be reached.");
      }
    }, 1500);

    return () => window.clearInterval(interval);
  }, [connectionMode, selectedRunId, selectedRun?.status]);

  function handleNumberControl(event) {
    const { name, value } = event.target;
    setControls((current) => ({
      ...current,
      [name]: Number(value),
    }));
  }

  function handleToggleControl(event) {
    const { name, checked } = event.target;
    setControls((current) => ({
      ...current,
      [name]: checked,
    }));
  }

  async function handleUploadSelection(event) {
    const file = event.target.files?.[0];
    if (!file) {
      return;
    }

    setIsUploading(true);
    setStatusMessage(`Uploading ${file.name}...`);
    try {
      const payload = await uploadMedia(file);
      setUploadedSource(payload);
      setInputMode("upload");
      setStatusMessage(`${payload.original_filename} uploaded. Ready to start analysis.`);
    } catch (error) {
      setStatusMessage(`Unable to upload media: ${error.message}`);
    } finally {
      setIsUploading(false);
      event.target.value = "";
    }
  }

  async function handleRunStart() {
    if (inputMode === "demo" && !selectedSource?.exists_locally) {
      setStatusMessage(
        "The selected demo clip is not available on the backend. Upload a local file or switch to a downloaded source first.",
      );
      return;
    }
    if (inputMode === "upload" && !uploadedSource?.source_path) {
      setStatusMessage("Upload a local video or image before starting analysis.");
      return;
    }

    setIsSubmitting(true);
    setStatusMessage("Submitting analysis run...");
    try {
      const record = await createRun({
        source_id: inputMode === "upload" ? `upload-${Date.now()}` : selectedSourceId,
        source_path: inputMode === "upload" ? uploadedSource.source_path : undefined,
        output_label: `operator-${Date.now()}`,
        controls,
      });
      setRuns((currentRuns) => [record, ...currentRuns.filter((item) => item.run_id !== record.run_id)]);
      setSelectedRunId(record.run_id);
      setStatusMessage("Analysis queued. Polling for progress updates.");
    } catch (error) {
      setStatusMessage(`Unable to start analysis: ${error.message}`);
    } finally {
      setIsSubmitting(false);
    }
  }

  async function handleExport() {
    if (!selectedRunId) {
      return;
    }
    setIsExporting(true);
    try {
      const payload = await exportCvat(selectedRunId);
      setStatusMessage(`CVAT bundle created at ${payload.archive_path}`);
    } catch (error) {
      setStatusMessage(`CVAT export failed: ${error.message}`);
    } finally {
      setIsExporting(false);
    }
  }

  return (
    <div className="app-shell">
      <div className="background-grid" />
      <header className="hero">
        <div className="hero-copy">
          <p className="eyebrow">Early Detection Maritime Targets</p>
          <h1>Smart Video Analytics Operator Console</h1>
          <p className="hero-text">
            React operator interface for a FastAPI + OpenCV + PyTorch pipeline that digitizes,
            enhances, detects, tracks, and exports maritime targets for review.
          </p>
        </div>
        <div className="hero-panel">
          <div className={`status-pill status-${connectionMode}`}>{connectionMode}</div>
          <p>{statusMessage}</p>
          <div className="stack-tags">
            <span>React</span>
            <span>FastAPI</span>
            <span>OpenCV</span>
            <span>PyTorch</span>
            <span>CUDA Ready</span>
            <span>CVAT Export</span>
          </div>
        </div>
      </header>

      <section className="metrics-grid">
        <MetricCard label="Frames Processed" value={summary?.frames_processed ?? "--"} />
        <MetricCard label="Processed FPS" value={summary?.processed_fps ?? "--"} accent="seafoam" />
        <MetricCard label="Unique Tracks" value={summary?.unique_tracks ?? "--"} accent="gold" />
        <MetricCard label="Active Alerts" value={summary?.active_alerts ?? "--"} accent="alert" />
      </section>

      <main className="workspace-grid">
        <section className="panel operator-panel">
          <PanelTitle
            title="Operator Controls"
            subtitle="Thresholds, disturbance simulation, and noise suppression."
          />

          <div className="mode-switch" role="tablist" aria-label="Input mode">
            <button
              className={`mode-button ${inputMode === "demo" ? "mode-button-active" : ""}`}
              type="button"
              onClick={() => setInputMode("demo")}
            >
              Demo Source
            </button>
            <button
              className={`mode-button ${inputMode === "upload" ? "mode-button-active" : ""}`}
              type="button"
              onClick={() => setInputMode("upload")}
            >
              Upload File
            </button>
          </div>

          {inputMode === "demo" ? (
            <>
              <label className="field">
                <span>Demo Source</span>
                <select
                  value={selectedSourceId}
                  onChange={(event) => setSelectedSourceId(event.target.value)}
                >
                  {sources.map((source) => (
                    <option key={source.id} value={source.id}>
                      {source.title}
                    </option>
                  ))}
                </select>
              </label>
              {!selectedSource?.exists_locally ? (
                <p className="field-note field-warning">
                  This demo clip is listed in the UI but is not stored on the backend yet.
                </p>
              ) : null}
            </>
          ) : (
            <div className="upload-card">
              <label className="field">
                <span>Local Video or Image</span>
                <input
                  type="file"
                  accept="video/*,image/*"
                  onChange={handleUploadSelection}
                  disabled={connectionMode !== "live" || isUploading}
                />
              </label>
              <p className="field-note">
                Upload MP4, MOV, WEBM, JPG, PNG, WEBP, or similar media from your system.
              </p>
              {uploadedSource ? (
                <div className="upload-summary">
                  <strong>{uploadedSource.original_filename}</strong>
                  <span>
                    {formatMediaKind(uploadedSource.media_kind)}
                    {uploadedSource.converted_to_video ? " · converted to MP4 for analysis" : ""}
                  </span>
                  {uploadedSource.note ? (
                    <p className="field-note field-warning">{uploadedSource.note}</p>
                  ) : null}
                  <button type="button" className="inline-link" onClick={() => setUploadedSource(null)}>
                    Remove upload
                  </button>
                </div>
              ) : null}
            </div>
          )}

          <div className="slider-grid">
            <RangeField
              label="Confidence Threshold"
              name="confidence_threshold"
              min="0.1"
              max="0.95"
              step="0.01"
              value={controls.confidence_threshold}
              onChange={handleNumberControl}
            />
            <RangeField
              label="Detection Interval"
              name="detection_interval"
              min="1"
              max="10"
              step="1"
              value={controls.detection_interval}
              onChange={handleNumberControl}
            />
            <RangeField
              label="Glare Suppression"
              name="glare_suppression"
              min="0"
              max="1"
              step="0.05"
              value={controls.glare_suppression}
              onChange={handleNumberControl}
            />
            <RangeField
              label="Sharpen Strength"
              name="sharpen_strength"
              min="0"
              max="1"
              step="0.05"
              value={controls.sharpen_strength}
              onChange={handleNumberControl}
            />
            <RangeField
              label="Temporal Smoothing"
              name="temporal_smoothing"
              min="0"
              max="0.8"
              step="0.05"
              value={controls.temporal_smoothing}
              onChange={handleNumberControl}
            />
            <RangeField
              label="Alert Area Ratio"
              name="alert_area_ratio"
              min="0.005"
              max="0.08"
              step="0.001"
              value={controls.alert_area_ratio}
              onChange={handleNumberControl}
            />
          </div>

          <label className="field">
            <span>Disturbance Profile</span>
            <select
              name="disturbance_profile"
              value={controls.disturbance_profile}
              onChange={(event) =>
                setControls((current) => ({ ...current, disturbance_profile: event.target.value }))
              }
            >
              <option value="clear">Clear</option>
              <option value="blurred">Blurred</option>
              <option value="hazy">Hazy</option>
              <option value="reflective">Reflective</option>
              <option value="mixed">Mixed</option>
            </select>
          </label>

          <div className="toggle-grid">
            <ToggleField
              name="enable_clahe"
              checked={controls.enable_clahe}
              onChange={handleToggleControl}
              label="Contrast recovery (CLAHE)"
            />
            <ToggleField
              name="enable_glare_mask"
              checked={controls.enable_glare_mask}
              onChange={handleToggleControl}
              label="Reflection suppression"
            />
            <ToggleField
              name="enable_temporal_smoothing"
              checked={controls.enable_temporal_smoothing}
              onChange={handleToggleControl}
              label="Temporal smoothing"
            />
            <ToggleField
              name="comparison_view"
              checked={controls.comparison_view}
              onChange={handleToggleControl}
              label="Split-screen comparison"
            />
          </div>

          <div className="action-row">
            <button
              className="primary-button"
              type="button"
              onClick={handleRunStart}
              disabled={!canStartAnalysis}
            >
              {isSubmitting ? "Queueing..." : "Start Analysis"}
            </button>
            <button
              className="secondary-button"
              type="button"
              onClick={handleExport}
              disabled={connectionMode !== "live" || isExporting || selectedRun?.status !== "completed"}
            >
              {isExporting ? "Exporting..." : "Export to CVAT"}
            </button>
          </div>
        </section>

        <section className="panel media-panel">
          <PanelTitle
            title="Detection and Tracking Output"
            subtitle="Annotated video, selected source metadata, and current run state."
          />

          <div className="source-card">
            <h3>{inputSource.title}</h3>
            <p>{inputSource.description}</p>
            <div className="source-meta">
              <span>{inputSource.license_name}</span>
              <span>{inputSource.exists_locally ? "ready for analysis" : "requires download"}</span>
            </div>
            {inputSource.note ? <p className="source-note">{inputSource.note}</p> : null}
            {inputSource.source_page ? (
              <a href={inputSource.source_page} target="_blank" rel="noreferrer">
                View source page
              </a>
            ) : null}
          </div>

          <div className="video-stage">
            {selectedRun?.artifacts?.output_video ? (
              <video
                controls
                className="result-video"
                poster={resolveMedia(selectedRun?.artifacts?.preview_image)}
                src={resolveMedia(selectedRun?.artifacts?.output_video)}
              />
            ) : (
              <div className="video-placeholder">
                <p>{selectedRun?.status === "failed" ? "The last analysis run failed." : "No processed video is available yet."}</p>
                <span>
                  {selectedRun?.status === "failed"
                    ? selectedRun?.error ?? "Check the selected input, runtime dependencies, and backend logs."
                    : "Once the FastAPI backend runs an analysis job, the annotated comparison video will appear here."}
                </span>
              </div>
            )}
          </div>

          <div className="timeline-strip">
            {timeline.map((item, index) => (
              <div key={`${item.frame_index}-${index}`} className="timeline-column">
                <div
                  className={`timeline-bar ${item.alerts?.length ? "timeline-alert" : ""}`}
                  style={{ height: `${32 + item.track_count * 18}px` }}
                />
                <span>{item.timestamp_seconds.toFixed(0)}s</span>
              </div>
            ))}
          </div>
        </section>

        <section className="panel intelligence-panel">
          <PanelTitle
            title="Tracks and Alerts"
            subtitle="Near-real-time track list, alert states, and workflow checkpoints."
          />

          <div className="run-strip">
            <div>
              <span className="mini-label">Selected Run</span>
              <strong>{selectedRun?.run_id ?? "none"}</strong>
            </div>
            <div>
              <span className="mini-label">Status</span>
              <strong>{selectedRun?.status ?? "idle"}</strong>
            </div>
            <div>
              <span className="mini-label">Progress</span>
              <strong>{Math.round((selectedRun?.progress ?? 0) * 100)}%</strong>
            </div>
            <div>
              <span className="mini-label">Device</span>
              <strong>{summary?.device ?? "--"}</strong>
            </div>
          </div>

          <div className="track-table">
            {tracks.length > 0 ? (
              tracks.map((track) => (
                <div key={track.track_id} className="track-row">
                  <div>
                    <span className="mini-label">Track</span>
                    <strong>T{track.track_id}</strong>
                  </div>
                  <div>
                    <span className="mini-label">Class</span>
                    <strong>{track.label}</strong>
                  </div>
                  <div>
                    <span className="mini-label">Confidence</span>
                    <strong>{track.confidence.toFixed(2)}</strong>
                  </div>
                  <div>
                    <span className="mini-label">State</span>
                    <strong className={`state-${track.alert_state}`}>{track.alert_state}</strong>
                  </div>
                </div>
              ))
            ) : (
              <div className="empty-card">
                No track data yet. Run a successful analysis to populate detections, tracks, and alerts.
              </div>
            )}
          </div>

          <div className="alert-stack">
            {alerts.map((alert, index) => (
              <div key={`${alert.track_id}-${index}`} className={`alert-card alert-${alert.severity}`}>
                <div className="alert-head">
                  <span>{alert.severity}</span>
                  <strong>T{alert.track_id}</strong>
                </div>
                <p>{alert.message}</p>
                <small>{alert.timestamp_seconds.toFixed(2)}s</small>
              </div>
            ))}
          </div>

          <div className="workflow-card">
            <h3>Operator Workflow</h3>
            <ol>
              <li>Select a downloaded maritime clip or upload local media.</li>
              <li>Adjust detection threshold and suppression controls based on sea state.</li>
              <li>Run analysis and review split-screen output with track overlays.</li>
              <li>Export sampled frames plus auto-boxes into CVAT for annotation refinement.</li>
            </ol>
          </div>
        </section>
      </main>
    </div>
  );
}

function MetricCard({ label, value, accent = "default" }) {
  return (
    <article className={`metric-card accent-${accent}`}>
      <span>{label}</span>
      <strong>{value}</strong>
    </article>
  );
}

function PanelTitle({ title, subtitle }) {
  return (
    <div className="panel-title">
      <div>
        <h2>{title}</h2>
        <p>{subtitle}</p>
      </div>
    </div>
  );
}

function RangeField({ label, value, ...props }) {
  return (
    <label className="field field-range">
      <div className="range-head">
        <span>{label}</span>
        <strong>{Number(value).toFixed(2)}</strong>
      </div>
      <input type="range" value={value} {...props} />
    </label>
  );
}

function ToggleField({ label, ...props }) {
  return (
    <label className="toggle-field">
      <input type="checkbox" {...props} />
      <span>{label}</span>
    </label>
  );
}

function buildRunStatusMessage(run) {
  if (run.status === "failed") {
    return run.error ? `Analysis failed: ${run.error}` : "Analysis failed. Check the selected input and backend logs.";
  }
  if (run.status === "completed") {
    return "Analysis completed. Review the annotated output and export if needed.";
  }
  if (run.status === "running") {
    return `Analysis running. ${Math.round((run.progress ?? 0) * 100)}% complete.`;
  }
  return "Analysis queued. Polling for progress updates.";
}

function formatMediaKind(mediaKind) {
  return mediaKind === "image" ? "Image upload" : "Video upload";
}

function resolveMedia(path) {
  if (!path) {
    return "";
  }
  if (path.startsWith("http")) {
    return path;
  }
  return `${API_BASE}${path}`;
}

export default App;
