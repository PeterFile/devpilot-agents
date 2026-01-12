import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { MainContent } from './components/layout/MainContent';

// Placeholder views
const Overview = () => <div className="p-4">Overview Dashboard (Coming Soon)</div>;
const Tasks = () => <div className="p-4">Task List (Coming Soon)</div>;
const Agents = () => <div className="p-4">Agent Status (Coming Soon)</div>;
const Reviews = () => <div className="p-4">Code Reviews (Coming Soon)</div>;
const Graph = () => <div className="p-4">Dependency Graph (Coming Soon)</div>;

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<MainContent />}>
          <Route index element={<Overview />} />
          <Route path="tasks" element={<Tasks />} />
          <Route path="agents" element={<Agents />} />
          <Route path="reviews" element={<Reviews />} />
          <Route path="graph" element={<Graph />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}

export default App;