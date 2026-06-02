import { EventEmitter } from 'events';

export class LogViewer extends EventEmitter {
    private logs: string[] = [];
    private readonly maxLogs: number = 1000;
    private readonly bufferThreshold: number = 100;

    handleIncomingLog(log: string) {
        this.logs.push(log);
        if (this.logs.length > this.maxLogs + this.bufferThreshold) {
            this.logs = this.logs.slice(-this.maxLogs);
        }
        this.emit('log', log);
    }

    getLogs(): string[] {
        return this.logs;
    }
}
