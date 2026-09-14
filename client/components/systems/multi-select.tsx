"use client";

import { Check, ChevronsUpDown, X } from "lucide-react";
import { useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Command,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
} from "@/components/ui/command";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { cn } from "@/lib/utils";

export interface Option {
  value: string;
  label: string;
  group?: string;
}

/**
 * Multi-select that also accepts free text.
 *
 * The backend matches on exact strings (`employment_screening`, `US-CA`), so the curated
 * options exist to get those right — but the vocabulary is open, so anything the user
 * types is kept.
 */
export function MultiSelect({
  options,
  value,
  onChange,
  placeholder = "Select…",
  allowCustom = true,
  id,
}: {
  options: Option[];
  value: string[];
  onChange: (value: string[]) => void;
  placeholder?: string;
  allowCustom?: boolean;
  id?: string;
}) {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");

  const toggle = (item: string) =>
    onChange(value.includes(item) ? value.filter((v) => v !== item) : [...value, item]);

  const trimmed = query.trim();
  const canAddCustom =
    allowCustom &&
    trimmed.length > 0 &&
    !options.some((o) => o.value.toLowerCase() === trimmed.toLowerCase()) &&
    !value.some((v) => v.toLowerCase() === trimmed.toLowerCase());

  const groups = Array.from(new Set(options.map((o) => o.group ?? "")));

  return (
    <div className="space-y-2">
      <Popover open={open} onOpenChange={setOpen}>
        <PopoverTrigger asChild>
          <Button
            id={id}
            type="button"
            variant="outline"
            role="combobox"
            aria-expanded={open}
            className="w-full justify-between font-normal"
          >
            <span className={cn("truncate", !value.length && "text-muted-foreground")}>
              {value.length ? `${value.length} selected` : placeholder}
            </span>
            <ChevronsUpDown className="ml-2 h-4 w-4 shrink-0 opacity-50" />
          </Button>
        </PopoverTrigger>
        <PopoverContent className="w-[--radix-popover-trigger-width] p-0" align="start">
          <Command shouldFilter>
            <CommandInput placeholder="Search or type a value…" value={query} onValueChange={setQuery} />
            <CommandList>
              <CommandEmpty>
                {allowCustom ? "Press Enter on “Add” below to use a custom value." : "No match."}
              </CommandEmpty>
              {canAddCustom ? (
                <CommandGroup>
                  <CommandItem
                    value={`add-${trimmed}`}
                    onSelect={() => {
                      onChange([...value, trimmed]);
                      setQuery("");
                    }}
                  >
                    Add “{trimmed}”
                  </CommandItem>
                </CommandGroup>
              ) : null}
              {groups.map((group) => {
                const groupOptions = options.filter((o) => (o.group ?? "") === group);
                if (!groupOptions.length) return null;
                return (
                  <CommandGroup key={group || "default"} heading={group || undefined}>
                    {groupOptions.map((option) => (
                      <CommandItem
                        key={option.value}
                        value={`${option.value} ${option.label}`}
                        onSelect={() => toggle(option.value)}
                      >
                        <Check
                          className={cn(
                            "mr-2 h-4 w-4",
                            value.includes(option.value) ? "opacity-100" : "opacity-0",
                          )}
                        />
                        {option.label}
                      </CommandItem>
                    ))}
                  </CommandGroup>
                );
              })}
            </CommandList>
          </Command>
        </PopoverContent>
      </Popover>

      {value.length ? (
        <div className="flex flex-wrap gap-1.5">
          {value.map((item) => (
            <Badge key={item} variant="secondary" className="gap-1 font-mono text-xs">
              {item}
              <button
                type="button"
                onClick={() => toggle(item)}
                aria-label={`Remove ${item}`}
                className="rounded-sm opacity-60 transition-opacity hover:opacity-100"
              >
                <X className="h-3 w-3" />
              </button>
            </Badge>
          ))}
        </div>
      ) : null}
    </div>
  );
}
