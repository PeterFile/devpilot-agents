import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import { ErrorMessage } from './ErrorMessage';

describe('ErrorMessage Component', () => {
  it('displays the error message', () => {
    const message = "Failed to load data";
    render(<ErrorMessage message={message} />);
    
    expect(screen.getByText(message)).toBeInTheDocument();
  });

  it('displays the title if provided', () => {
    const title = "Critical Error";
    render(<ErrorMessage message="msg" title={title} />);
    
    expect(screen.getByText(title)).toBeInTheDocument();
  });

  it('calls onRetry when retry button is clicked', () => {
    const onRetry = vi.fn();
    render(<ErrorMessage message="msg" onRetry={onRetry} />);
    
    const button = screen.getByRole('button', { name: /try again/i });
    fireEvent.click(button);
    
    expect(onRetry).toHaveBeenCalledTimes(1);
  });

  it('does not render retry button if onRetry is not provided', () => {
    render(<ErrorMessage message="msg" />);
    
    const button = screen.queryByRole('button', { name: /try again/i });
    expect(button).not.toBeInTheDocument();
  });
});
