import { create } from "zustand";

interface SessionState {
  accessToken: string | null;
  setAccessToken: (token: string) => void;
  clear: () => void;
}

export const useSession = create<SessionState>((set) => ({
  accessToken: null,
  setAccessToken: (accessToken) => set({ accessToken }),
  clear: () => set({ accessToken: null }),
}));
