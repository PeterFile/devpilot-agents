import React from 'react';
import { NavLink } from 'react-router-dom';
import { 
  LayoutDashboard, 
  ListTodo, 
  Bot, 
  FileSearch, 
  Network 
} from 'lucide-react';
import { clsx } from 'clsx';

const NAV_ITEMS = [
  { label: 'Overview', path: '/', icon: LayoutDashboard },
  { label: 'Tasks', path: '/tasks', icon: ListTodo },
  { label: 'Agents', path: '/agents', icon: Bot },
  { label: 'Reviews', path: '/reviews', icon: FileSearch },
  { label: 'Graph', path: '/graph', icon: Network },
];

export const Sidebar: React.FC = () => {
  return (
    <aside className="w-64 bg-gray-950 border-r border-gray-800 flex flex-col">
      <nav className="flex-1 p-4 space-y-1">
        {NAV_ITEMS.map((item) => (
          <NavLink
            key={item.path}
            to={item.path}
            className={({ isActive }) => clsx(
              "flex items-center gap-3 px-3 py-2 rounded-md transition-colors duration-200 group",
              isActive 
                ? "bg-blue-500/10 text-blue-400" 
                : "text-gray-400 hover:text-gray-100 hover:bg-gray-900"
            )}
          >
            <item.icon className="w-4 h-4" />
            <span className="text-sm font-medium">{item.label}</span>
          </NavLink>
        ))}
      </nav>
      
      <div className="p-4 border-t border-gray-800">
        <div className="text-xs text-gray-600 text-center">
          v0.1.0-alpha
        </div>
      </div>
    </aside>
  );
};
