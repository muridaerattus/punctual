import type { HttpClient } from '../../shared/api/client';
import type { BoardInfo, LeaseAction, LeaseResult, Task, TaskChanges, TaskInput } from './types';

export class TaskApi {
  constructor(private client: HttpClient) {}

  boards() {
    return this.client.request<BoardInfo[]>('/boards');
  }
  createBoard(name: string, prefix: string) {
    return this.client.request<BoardInfo>('/boards', 'POST', { name, prefix });
  }
  list(boardId = 1) {
    return this.client.request<Task[]>(`/tasks?board_id=${boardId}`);
  }
  create(input: TaskInput, boardId = 1) {
    return this.client.request<Task>('/tasks', 'POST', { ...input, board_id: boardId });
  }
  update(id: number, changes: TaskChanges) {
    return this.client.request<Task>(`/tasks/${id}`, 'PATCH', changes);
  }
  delete(id: number, revision: number, leaseToken?: string) {
    return this.client.request<{ deleted: number }>(`/tasks/${id}`, 'DELETE', {
      revision,
      lease_token: leaseToken,
    });
  }
  lease(id: number, action: LeaseAction, owner: string, leaseToken?: string) {
    return this.client.request<LeaseResult>(`/tasks/${id}/${action}`, 'POST', {
      owner,
      lease_token: leaseToken,
      seconds: 900,
    });
  }
}
