export const statuses = ['To Do', 'In Progress', 'Complete'] as const;
export type Status = (typeof statuses)[number];
export type LeaseAction = 'claim' | 'renew' | 'release';

export interface Task {
  id: number;
  board_id: number;
  number: number;
  key: string;
  parent_key: string | null;
  title: string;
  description: string;
  status: Status;
  assignee: string | null;
  parent_id: number | null;
  revision: number;
  lease_owner: string | null;
  lease_expires_at: number | null;
}

export type TaskInput = Pick<Task, 'title' | 'description' | 'status' | 'assignee' | 'parent_id'>;
export type TaskChanges = Partial<TaskInput> & { revision: number; lease_token?: string };
export type LeaseResult = Task & { lease_token?: string };
