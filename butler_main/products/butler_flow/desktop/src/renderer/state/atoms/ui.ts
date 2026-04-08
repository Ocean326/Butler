import { atom } from "jotai";

export type ConversationLens = "mission" | "studio" | "recovery";
export type DetailTab = "summary" | "artifacts" | "runtime" | "roles";

export const conversationLensAtom = atom<ConversationLens>("mission");
export const actionDraftAtom = atom("");
export const statusMessageAtom = atom("");
