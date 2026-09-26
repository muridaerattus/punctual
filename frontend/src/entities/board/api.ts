import type { HttpClient } from '../../shared/api/client';
import type { BoardInfo } from './types';

export class BoardApi {
  constructor(private client: HttpClient) {}

  list() {
    return this.client.request<BoardInfo[]>('/boards');
  }
  create(name: string, prefix: string) {
    return this.client.request<BoardInfo>('/boards', 'POST', { name, prefix });
  }
}
