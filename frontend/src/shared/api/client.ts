export class ApiError extends Error {
  constructor(
    message: string,
    public status: number,
  ) {
    super(message);
  }
}

export class HttpClient {
  constructor(
    private getKey: () => string,
    private onUnauthorized: () => void,
  ) {}

  async request<T>(path: string, method = 'GET', body?: unknown): Promise<T> {
    const response = await fetch('/api' + path, {
      method,
      headers: {
        Authorization: `Bearer ${this.getKey()}`,
        'Content-Type': 'application/json',
      },
      ...(body === undefined ? {} : { body: JSON.stringify(body) }),
    });
    const data = await response.json();
    if (!response.ok) {
      if (response.status === 401) this.onUnauthorized();
      const message =
        data.error?.message ||
        data.detail?.map?.((detail: { msg: string }) => detail.msg).join('; ') ||
        'Request failed';
      throw new ApiError(message, response.status);
    }
    return data as T;
  }
}
