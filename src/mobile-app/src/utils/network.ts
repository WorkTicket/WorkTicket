import NetInfo, { NetInfoState } from "@react-native-community/netinfo";

let _listeners: Set<(online: boolean) => void> = new Set();
let _lastOnline: boolean = true;

export function isOnline(): boolean {
  return _lastOnline;
}

export async function checkConnectivity(): Promise<boolean> {
  try {
    const state = await NetInfo.fetch();
    _lastOnline = state.isConnected ?? true;
    return _lastOnline;
  } catch (err) {
    console.error("checkConnectivity failed:", err);
    return true;
  }
}

export function subscribeToConnectivity(callback: (online: boolean) => void): () => void {
  _listeners.add(callback);
  callback(_lastOnline);
  return () => { _listeners.delete(callback); };
}

NetInfo.addEventListener((state: NetInfoState) => {
  _lastOnline = state.isConnected ?? true;
  for (const cb of _listeners) {
    try { cb(_lastOnline); } catch (err) { console.error("connectivity callback error:", err); }
  }
});
