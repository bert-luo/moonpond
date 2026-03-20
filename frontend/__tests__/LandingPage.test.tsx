import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { LandingPage } from '@/app/components/LandingPage';

describe('LandingPage', () => {
  it('renders prompt input and submit button', () => {
    render(<LandingPage onSubmit={vi.fn()} isGenerating={false} />);
    expect(screen.getByRole('textbox')).toBeDefined();
    expect(screen.getByRole('button', { name: 'Generate Game' })).toBeDefined();
  });

  it('shows carousel placeholder when input is empty', () => {
    render(<LandingPage onSubmit={vi.fn()} isGenerating={false} />);
    // First example prompt should appear as placeholder text
    expect(screen.getByText('A space shooter where you dodge asteroids')).toBeDefined();
  });

  it('hides carousel placeholder when user types', () => {
    render(<LandingPage onSubmit={vi.fn()} isGenerating={false} />);
    const input = screen.getByRole('textbox') as HTMLInputElement;
    fireEvent.change(input, { target: { value: 'my game' } });
    expect(screen.queryByText('A space shooter where you dodge asteroids')).toBeNull();
  });

  it('submit calls onSubmit with the prompt text', () => {
    const onSubmit = vi.fn();
    render(<LandingPage onSubmit={onSubmit} isGenerating={false} />);
    const input = screen.getByRole('textbox') as HTMLInputElement;
    fireEvent.change(input, { target: { value: 'my cool game' } });
    fireEvent.submit(input.closest('form')!);
    expect(onSubmit).toHaveBeenCalledWith('my cool game');
  });

  it('submit button shows "Generating..." and is disabled when isGenerating=true', () => {
    render(<LandingPage onSubmit={vi.fn()} isGenerating={true} />);
    const button = screen.getByRole('button', { name: 'Generating...' });
    expect(button).toBeDefined();
    expect((button as HTMLButtonElement).disabled).toBe(true);
  });
});
