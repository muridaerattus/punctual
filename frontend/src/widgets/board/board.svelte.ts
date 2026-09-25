import type { TaskApi } from '../../entities/task/api';
import type { LeaseState } from '../../entities/task/lease-state.svelte';
import {
  statuses,
  type LeaseAction,
  type Status,
  type Task,
  type TaskInput,
} from '../../entities/task/types';

export class Board {
  constructor(
    private api: TaskApi,
    readonly leases: LeaseState,
    initialTasks: Task[],
  ) {
    this.tasks = initialTasks;
    this.selected = initialTasks[0]?.id ?? null;
  }
  tasks = $state<Task[]>([]);
  search = $state('');
  selected = $state<number | null>(null);
  busy = $state(false);
  error = $state('');
  notice = $state('');
  filtered = $derived(
    this.tasks.filter((task) =>
      `${task.title} ${task.description} ${task.assignee || ''} #${task.id}`
        .toLowerCase()
        .includes(this.search.toLowerCase()),
    ),
  );
  ordered = $derived(
    statuses.flatMap((status) => this.filtered.filter((task) => task.status === status)),
  );
  current = $derived(this.tasks.find((task) => task.id === this.selected));
  completion = $derived(
    this.tasks.length
      ? Math.round(
          (this.tasks.filter((task) => task.status === 'Complete').length / this.tasks.length) *
            100,
        )
      : 0,
  );

  private report(error: unknown) {
    this.error = error instanceof Error ? error.message : 'Request failed';
  }

  private async run<T>(action: () => Promise<T>): Promise<T | undefined> {
    if (this.busy) return;
    this.busy = true;
    this.error = '';
    this.notice = '';
    try {
      return await action();
    } catch (error) {
      this.report(error);
    } finally {
      this.busy = false;
    }
  }

  private async load() {
    this.tasks = await this.api.list();
    if (!this.tasks.some((task) => task.id === this.selected))
      this.selected = this.tasks[0]?.id ?? null;
  }

  refresh() {
    return this.run(() => this.load());
  }

  async poll() {
    try {
      await this.load();
    } catch (error) {
      this.report(error);
    }
  }

  save(input: TaskInput, original?: Task) {
    return this.run(async () => {
      const task = original
        ? await this.api.update(original.id, {
            ...input,
            revision: original.revision,
            lease_token: this.leases.tokens[original.id],
          })
        : await this.api.create(input);
      await this.load();
      this.selected = task.id;
      this.notice = 'Task saved';
      return task;
    });
  }

  move(status: Status) {
    const task = this.current;
    if (!task) return;
    return this.run(async () => {
      await this.api.update(task.id, {
        status,
        revision: task.revision,
        lease_token: this.leases.tokens[task.id],
      });
      await this.load();
      this.notice = `Moved to ${status}`;
    });
  }

  lease(action: LeaseAction) {
    const task = this.current;
    if (!task) return;
    return this.run(async () => {
      const result = await this.api.lease(
        task.id,
        action,
        this.leases.owner,
        this.leases.tokens[task.id],
      );
      this.leases.saveToken(task.id, result.lease_token);
      await this.load();
      this.notice = action === 'release' ? 'Lease released' : 'Lease active for 15 minutes';
    });
  }

  remove(task: Task) {
    return this.run(async () => {
      await this.api.delete(task.id, task.revision, this.leases.tokens[task.id]);
      this.leases.saveToken(task.id);
      await this.load();
      this.notice = 'Task deleted';
      return true;
    });
  }

  navigate(delta: number) {
    if (!this.ordered.length) return;
    const index = this.ordered.findIndex((task) => task.id === this.selected);
    this.selected = this.ordered[Math.max(0, Math.min(this.ordered.length - 1, index + delta))].id;
  }
}
