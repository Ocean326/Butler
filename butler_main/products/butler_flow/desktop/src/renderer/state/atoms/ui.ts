import { atom } from "jotai";

export type DesktopPage = "home" | "flow" | "manage";
export type DetailTab = "summary" | "artifacts" | "runtime" | "roles";

export const activePageAtom = atom<DesktopPage>("home");
export const detailTabAtom = atom<DetailTab>("summary");
export const actionDraftAtom = atom("");
export const statusMessageAtom = atom("");
