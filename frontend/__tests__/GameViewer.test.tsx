import { describe, it } from 'vitest';

describe('GameViewer', () => {
  it.todo('renders idle placeholder when status is idle and no gameUrl');
  it.todo('renders shimmer skeleton when status is generating');
  it.todo('renders iframe with gameUrl when game is loaded');
  it.todo('iframe has allow="cross-origin-isolated" attribute');
  it.todo('keeps previous game visible on error if gameUrl exists');
});
