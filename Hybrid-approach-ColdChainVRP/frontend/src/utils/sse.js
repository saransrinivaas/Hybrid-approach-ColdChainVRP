import { API_BASE } from '../data';

export function runSSE(endpoint, setLogs, setRunning, onDone) {
  setRunning(true);
  setLogs([]);
  const es = new EventSource(`${API_BASE}${endpoint}`);
  es.onmessage = (event) => {
    const data = JSON.parse(event.data);
    if (data.status === 'DONE') {
      es.close();
      setRunning(false);
      if (onDone) onDone();
    } else if (data.message) {
      setLogs((prev) => [...prev, data.message]);
    }
  };
  es.onerror = () => {
    es.close();
    setRunning(false);
    setLogs((prev) => [...prev, 'ERROR: Connection to backend failed. Is Flask running on port 5000?']);
  };
}
