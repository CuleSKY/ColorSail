import { mkdir, readTextFile, writeTextFile } from "@tauri-apps/plugin-fs";
import { appDataDir, join } from "@tauri-apps/plugin-path";

type CacheEntry<T> = {
  etag: string | null;
  data: T;
};

type StorageDriver = {
  read: <T>(key: string) => Promise<CacheEntry<T> | null>;
  write: <T>(key: string, entry: CacheEntry<T>) => Promise<void>;
};

export const createTauriStorageDriver = async (): Promise<StorageDriver> => {
  const appDir = await appDataDir();
  const baseDir = await join(appDir, "resources");
  try {
    await mkdir(baseDir, { recursive: true });
  } catch {
    // ignore
  }
  return {
    read: async <T>(key: string) => {
      try {
        const filePath = await join(baseDir, `${key}.json`);
        const raw = await readTextFile(filePath);
        return JSON.parse(raw) as CacheEntry<T>;
      } catch {
        return null;
      }
    },
    write: async <T>(key: string, entry: CacheEntry<T>) => {
      const filePath = await join(baseDir, `${key}.json`);
      await writeTextFile(filePath, JSON.stringify(entry));
    }
  };
};
