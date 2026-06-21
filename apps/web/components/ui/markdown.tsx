"use client";

import type { ReactNode } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

import { cn } from "@/lib/utils";

interface Props {
  children: string;
  className?: string;
}

type WithChildren = { children?: ReactNode };
type WithChildrenAndHref = WithChildren & { href?: string };
type WithChildrenAndClass = WithChildren & { className?: string };

/** Compact markdown renderer used by the NL "text" answer. GFM
 *  enables tables / strikethrough / autolinks. Each tag is mapped to
 *  a Tailwind-styled element — no @tailwindcss/typography dependency. */
export function Markdown({ children, className }: Props) {
  return (
    <div className={cn("text-sm leading-relaxed text-slate-700", className)}>
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          h1: ({ children }: WithChildren) => (
            <h1 className="mb-2 mt-4 text-base font-semibold text-slate-900">
              {children}
            </h1>
          ),
          h2: ({ children }: WithChildren) => (
            <h2 className="mb-2 mt-4 text-sm font-semibold text-slate-900">
              {children}
            </h2>
          ),
          h3: ({ children }: WithChildren) => (
            <h3 className="mb-1 mt-3 text-sm font-semibold text-slate-800">
              {children}
            </h3>
          ),
          p: ({ children }: WithChildren) => (
            <p className="my-2 first:mt-0 last:mb-0">{children}</p>
          ),
          ul: ({ children }: WithChildren) => (
            <ul className="my-2 ml-5 list-disc space-y-1">{children}</ul>
          ),
          ol: ({ children }: WithChildren) => (
            <ol className="my-2 ml-5 list-decimal space-y-1">{children}</ol>
          ),
          li: ({ children }: WithChildren) => (
            <li className="pl-1">{children}</li>
          ),
          strong: ({ children }: WithChildren) => (
            <strong className="font-semibold text-slate-900">{children}</strong>
          ),
          em: ({ children }: WithChildren) => (
            <em className="italic">{children}</em>
          ),
          code: ({ children, className }: WithChildrenAndClass) => {
            // Block code (```lang ... ```) has a `language-*` class.
            if (className?.startsWith("language-")) {
              return (
                <code className="block overflow-x-auto rounded bg-slate-50 p-3 font-mono text-xs text-slate-800">
                  {children}
                </code>
              );
            }
            return (
              <code className="rounded bg-slate-100 px-1 py-0.5 font-mono text-[12px] text-slate-800">
                {children}
              </code>
            );
          },
          pre: ({ children }: WithChildren) => <pre className="my-2">{children}</pre>,
          hr: () => <hr className="my-3 border-slate-200" />,
          a: ({ children, href }: WithChildrenAndHref) => (
            <a
              href={href}
              className="text-primary underline underline-offset-2 hover:text-primary/80"
              target="_blank"
              rel="noopener noreferrer"
            >
              {children}
            </a>
          ),
          blockquote: ({ children }: WithChildren) => (
            <blockquote className="my-2 border-l-2 border-slate-200 pl-3 text-slate-600">
              {children}
            </blockquote>
          ),
          table: ({ children }: WithChildren) => (
            <div className="my-3 overflow-x-auto rounded border border-slate-200">
              <table className="w-full text-xs">{children}</table>
            </div>
          ),
          thead: ({ children }: WithChildren) => (
            <thead className="border-b bg-slate-50 text-left font-medium text-slate-700">
              {children}
            </thead>
          ),
          th: ({ children }: WithChildren) => <th className="px-2 py-1.5">{children}</th>,
          td: ({ children }: WithChildren) => (
            <td className="border-t px-2 py-1.5 align-top">{children}</td>
          ),
        }}
      >
        {children}
      </ReactMarkdown>
    </div>
  );
}
