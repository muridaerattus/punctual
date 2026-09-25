import type { Status, Task } from '../../entities/task/types';

export interface EditorOptions {
  task?: Task;
  parentId?: number;
  status?: Status;
}
