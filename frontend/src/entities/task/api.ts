import type { HttpClient } from '../../shared/api/client';
import type { LeaseAction, LeaseResult, Task, TaskChanges, TaskInput } from './types';

export class TaskApi {
  constructor(private client: HttpClient) {}

  list() {
    return this.client.request<Task[]>('/tasks');
  }
  create(input: TaskInput) {
    return this.client.request<Task>('/tasks', 'POST', input);
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
