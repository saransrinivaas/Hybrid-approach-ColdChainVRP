import { Terminal, Activity, Play } from 'lucide-react';

/**
 * Live-output terminal panel.
 * @param {object} props
 * @param {string[]} props.logs
 * @param {import('react').RefObject} props.logsEndRef
 * @param {boolean} props.isRunning
 * @param {() => void} [props.onRun]
 * @param {string} props.btnLabel
 * @param {string} props.idleText
 * @param {string} [props.height]
 * @param {boolean} [props.hideRunButton] — when actions live elsewhere (e.g. Compare tab header)
 */
export default function TerminalPanel({
  logs,
  logsEndRef,
  isRunning,
  onRun,
  btnLabel,
  idleText,
  height = '280px',
  hideRunButton = false,
}) {
  return (
    <div className="terminal-wrap" style={{ height, display: 'flex', flexDirection: 'column' }}>
      <div className="terminal-head">
        <h3>
          <Terminal size={15} strokeWidth={2} aria-hidden />
          Pipeline output
        </h3>
        {!hideRunButton && onRun && (
          <button
            type="button"
            className="btn btn-primary"
            onClick={onRun}
            disabled={isRunning}
          >
            {isRunning ? <Activity size={15} /> : <Play size={15} />}
            {isRunning ? 'Running…' : btnLabel}
          </button>
        )}
      </div>
      <div
        className="terminal-body"
        style={{ flex: 1, maxHeight: hideRunButton ? '100%' : undefined }}
      >
        {logs.length === 0 && !isRunning && (
          <span className="terminal-idle">{idleText}</span>
        )}
        {logs.map((log, i) => (
          <div key={i} style={{ marginBottom: '0.12rem', opacity: log.includes('OK') ? 1 : 0.82 }}>
            {log}
          </div>
        ))}
        <div ref={logsEndRef} />
      </div>
    </div>
  );
}
