import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { LandingPage } from '@/app/components/LandingPage';

describe('LandingPage', () => {
  it('renders prompt input and submit button', () => {
    render(<LandingPage onSubmit={vi.fn()} isGenerating={false} />);
    expect(screen.getByPlaceholderText('Describe a game...')).toBeDefined();
    expect(screen.getByRole('button', { name: 'Generate Game' })).toBeDefined();
  });

  it('clicking an example prompt fills the input', () => {
    render(<LandingPage onSubmit={vi.fn()} isGenerating={false} />);
    const chip = screen.getByText('A space shooter where you dodge asteroids');
    fireEvent.click(chip);
    const input = screen.getByPlaceholderText('Describe a game...') as HTMLInputElement;
    expect(input.value).toBe('A space shooter where you dodge asteroids');
  });

  it('submit calls onSubmit with the prompt text', () => {
    const onSubmit = vi.fn();
    render(<LandingPage onSubmit={onSubmit} isGenerating={false} />);
    const input = screen.getByPlaceholderText('Describe a game...') as HTMLInputElement;
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
