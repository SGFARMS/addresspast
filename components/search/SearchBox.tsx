"use client";

import { useEffect, useId, useRef, useState } from "react";
import { useTranslations } from "next-intl";
import { ArrowRight, LoaderCircle, LocateFixed, MapPin, Mic, Search, X } from "lucide-react";
import { siteConfig } from "@/site.config";
import { track } from "@/lib/analytics";
import type { Place } from "@/lib/types";

interface Props {
  onPlace: (p: Place) => void;
  onAsk: (q: string) => Promise<void>;
  onLocate: () => void;
  busy?: boolean;
  initial?: string;
}

type SpeechCtor = new () => {
  lang: string;
  interimResults: boolean;
  maxAlternatives: number;
  start: () => void;
  stop: () => void;
  onresult: ((e: { results: ArrayLike<ArrayLike<{ transcript: string }>> }) => void) | null;
  onend: (() => void) | null;
  onerror: (() => void) | null;
};

/** Looks like a question rather than an address: no leading house number and contains a query word. */
export function looksLikeQuestion(q: string) {
  if (/^\s*\d+\s+\w/.test(q)) return false;
  return /\b(fires?|deaths?|died|murders?|homicides?|accidents?|drug|meth|labs?|flood|anything|records?|before|after|since|last|near|incendios?|muertes?|antes|despu[eé]s|desde|cerca|[uú]ltimos)\b|\?/i.test(q);
}

export function SearchBox({ onPlace, onAsk, onLocate, busy, initial = "" }: Props) {
  const t = useTranslations("search");
  const [q, setQ] = useState(initial);
  const [items, setItems] = useState<Place[]>([]);
  const [open, setOpen] = useState(false);
  const [active, setActive] = useState(-1);
  const [loading, setLoading] = useState(false);
  const [note, setNote] = useState<string | null>(null);
  const [listening, setListening] = useState(false);
  const [voiceOk, setVoiceOk] = useState(false);
  const listId = useId();
  const inputRef = useRef<HTMLInputElement>(null);
  const abort = useRef<AbortController | null>(null);
  const recog = useRef<InstanceType<SpeechCtor> | null>(null);
  const justChose = useRef(false);

  useEffect(() => {
    const w = window as unknown as { SpeechRecognition?: SpeechCtor; webkitSpeechRecognition?: SpeechCtor };
    setVoiceOk(Boolean(siteConfig.features.voiceSearch && (w.SpeechRecognition || w.webkitSpeechRecognition)));
  }, []);

  // Debounced autocomplete through our cached server route
  useEffect(() => {
    const text = q.trim();
    if (justChose.current) {
      justChose.current = false;
      return;
    }
    if (text.length < 3 || looksLikeQuestion(text)) {
      setItems([]);
      setLoading(false);
      return;
    }
    const timer = setTimeout(async () => {
      abort.current?.abort();
      const ctrl = new AbortController();
      abort.current = ctrl;
      setLoading(true);
      try {
        const res = await fetch(`/api/places/suggest?q=${encodeURIComponent(text)}`, { signal: ctrl.signal });
        const json = await res.json();
        if (res.status === 429) setNote(t("noResults"));
        setItems(json.places ?? []);
        setOpen(true);
        setActive(-1);
      } catch {
        /* aborted */
      } finally {
        if (!ctrl.signal.aborted) setLoading(false);
      }
    }, 280);
    return () => clearTimeout(timer);
  }, [q, t]);

  const choose = (p: Place) => {
    justChose.current = true;
    abort.current?.abort();
    setQ(p.label);
    setOpen(false);
    setItems([]);
    setNote(null);
    track("search", { kind: "address" });
    onPlace(p);
  };

  const submit = async () => {
    const text = q.trim();
    if (!text) return;
    if (active >= 0 && items[active]) return choose(items[active]);
    if (!looksLikeQuestion(text) && items[0]) return choose(items[0]);
    setOpen(false);
    setNote(null);
    track("search", { kind: "question" });
    await onAsk(text);
  };

  const startVoice = () => {
    const w = window as unknown as { SpeechRecognition?: SpeechCtor; webkitSpeechRecognition?: SpeechCtor };
    const Ctor = w.SpeechRecognition ?? w.webkitSpeechRecognition;
    if (!Ctor) return setNote(t("voiceUnsupported"));
    if (listening) return recog.current?.stop();
    const r = new Ctor();
    r.lang = document.documentElement.lang === "es" ? "es-US" : "en-US";
    r.interimResults = false;
    r.maxAlternatives = 1;
    r.onresult = (e) => {
      const text = e.results[0]?.[0]?.transcript ?? "";
      setQ(text);
      track("search", { kind: "voice" });
      if (text) void (looksLikeQuestion(text) ? onAsk(text) : Promise.resolve(setOpen(true)));
    };
    r.onend = () => setListening(false);
    r.onerror = () => setListening(false);
    recog.current = r;
    setListening(true);
    r.start();
  };

  const showHint = open && q.trim().length >= 3 && (looksLikeQuestion(q) || (!loading && items.length === 0));

  return (
    <div className="relative">
      <form
        role="search"
        onSubmit={(e) => {
          e.preventDefault();
          void submit();
        }}
        className="flex items-center gap-1 rounded-2xl border border-line bg-surface p-1.5 shadow-card focus-within:border-accent"
      >
        <label htmlFor={`${listId}-input`} className="sr-only">
          {t("label")}
        </label>
        <Search size={20} className="ml-1.5 shrink-0 text-ink-3" aria-hidden />
        <input
          ref={inputRef}
          id={`${listId}-input`}
          type="text"
          inputMode="search"
          enterKeyHint="search"
          autoComplete="off"
          spellCheck={false}
          value={q}
          placeholder={t("placeholder")}
          onChange={(e) => {
            justChose.current = false;
            setQ(e.target.value);
            setOpen(true);
          }}
          onFocus={() => setOpen(true)}
          onBlur={() => setTimeout(() => setOpen(false), 150)}
          onKeyDown={(e) => {
            if (e.key === "ArrowDown") { e.preventDefault(); setActive((a) => Math.min(items.length - 1, a + 1)); }
            if (e.key === "ArrowUp") { e.preventDefault(); setActive((a) => Math.max(-1, a - 1)); }
            if (e.key === "Escape") setOpen(false);
          }}
          role="combobox"
          aria-expanded={open && items.length > 0}
          aria-controls={listId}
          aria-autocomplete="list"
          aria-activedescendant={active >= 0 ? `${listId}-${active}` : undefined}
          className="min-w-0 flex-1 bg-transparent px-1.5 py-2.5 text-base text-ink placeholder:text-ink-3 focus:outline-none"
        />
        {(loading || busy) && <LoaderCircle size={18} className="shrink-0 animate-spin text-ink-3" aria-hidden />}
        {q && !busy && (
          <button type="button" onClick={() => { setQ(""); setItems([]); inputRef.current?.focus(); }} aria-label={t("clear")} className="rounded-lg p-2 text-ink-3 hover:bg-surface-2 hover:text-ink">
            <X size={18} aria-hidden />
          </button>
        )}
        {voiceOk && (
          <button
            type="button"
            onClick={startVoice}
            aria-label={listening ? t("voiceListening") : t("voice")}
            aria-pressed={listening}
            className={`rounded-lg p-2 ${listening ? "bg-adobe-soft text-adobe" : "text-ink-2 hover:bg-surface-2 hover:text-ink"}`}
          >
            <Mic size={18} aria-hidden />
          </button>
        )}
        <button type="button" onClick={onLocate} aria-label={t("locate")} title={t("locate")} className="rounded-lg p-2 text-ink-2 hover:bg-surface-2 hover:text-ink">
          <LocateFixed size={18} aria-hidden />
        </button>
        <button type="submit" aria-label={t("submit")} title={t("submit")} className="rounded-xl bg-accent p-2.5 text-accent-ink hover:opacity-90">
          <ArrowRight size={18} aria-hidden />
        </button>
      </form>

      {open && items.length > 0 && (
        <ul id={listId} role="listbox" aria-label={t("suggestions")} className="absolute inset-x-0 top-full z-30 mt-1 overflow-hidden rounded-xl border border-line bg-surface shadow-card">
          {items.map((p, i) => (
            <li
              key={`${p.label}-${i}`}
              id={`${listId}-${i}`}
              role="option"
              aria-selected={i === active}
              onMouseDown={(e) => { e.preventDefault(); choose(p); }}
              onMouseEnter={() => setActive(i)}
              className={`flex cursor-pointer items-center gap-2 px-3 py-2.5 text-sm ${i === active ? "bg-surface-2" : ""}`}
            >
              <MapPin size={16} className="shrink-0 text-ink-3" aria-hidden />
              <span className="truncate">{p.label}</span>
            </li>
          ))}
        </ul>
      )}
      {showHint && items.length === 0 && (
        <p className="mt-2 px-2 text-xs text-ink-3" aria-live="polite">{t("askHint")}</p>
      )}
      {listening && <p className="mt-2 px-2 text-xs text-adobe" aria-live="assertive">{t("voiceListening")}</p>}
      {note && <p className="mt-2 px-2 text-xs text-ink-2" aria-live="polite">{note}</p>}
    </div>
  );
}
