import { useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useQueryClient } from '@tanstack/react-query'
import {
  AlertTriangle, BedDouble, Building2, Car, Download, FileText, IndianRupee, LayoutGrid, List, Loader2, MapPin, Ruler, Table2, Trash2
} from 'lucide-react'
import { format } from 'date-fns'
import { toast } from 'sonner'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { useDeleteListingsMutation, useFacetsQuery, useListingsQuery, useSourceQuery } from '@/lib/api'
import type { ListingResult, ListingsQuery } from '@/types/api'

// --- Utilities ---
const humanize = (str?: string | null) => 
  str ? str.replace(/[-_]/g, ' ').replace(/\w\S*/g, (t) => t.charAt(0).toUpperCase() + t.substring(1).toLowerCase()) : ''

const formatPriceNum = (value?: number | null) => {
  if (!value) return '—'
  return new Intl.NumberFormat('en-IN', { style: 'currency', currency: 'INR', maximumFractionDigits: 0 }).format(value)
}

const formatPricePerSqft = (price: number) => 
  new Intl.NumberFormat('en-IN', { style: 'currency', currency: 'INR', maximumFractionDigits: 0 }).format(price) + '/sqft'

const formatPriceRange = (min?: number | null, max?: number | null, status?: string | null) => {
  if (min && max && min !== max) return `${formatPriceNum(min)} – ${formatPriceNum(max)}`
  if (min) return formatPriceNum(min)
  if (max) return formatPriceNum(max)
  return status ? humanize(status) : 'Call for Price'
}

type PsfSummary = { kind: 'rate_only'; rate: number } | { kind: 'converted'; rate: number; area: number; areaLabel: string } | null
const perSqftSummary = (listing: ListingResult): PsfSummary => {
  if (listing.price_per_sqft && !listing.sqft) return { kind: 'rate_only', rate: listing.price_per_sqft }
  if (listing.price_per_sqft && listing.sqft) return { kind: 'converted', rate: listing.price_per_sqft, area: listing.sqft, areaLabel: 'sqft' }
  return null
}

function listingTitle(listing: ListingResult): string {
  const area = listing.canonical_location || listing.location
  const spec = listing.bhk != null ? `${listing.bhk} BHK` : humanize(listing.property_type)
  if (listing.listing_intent === 'REQUEST') {
    return `${spec} requirement${area ? ` · ${area}` : ''}`
  }
  return `${spec}${area ? ` · ${area}` : ''}`
}

function compactFacts(listing: ListingResult) {
  return [
    listing.furnishing ? humanize(listing.furnishing) : null,
    listing.floor_band ? `${humanize(listing.floor_band)} floor` : null,
    listing.pets_allowed === true ? 'Pets allowed' : listing.pets_allowed === false ? 'No pets' : null,
    listing.has_contact ? 'Has contact' : null,
  ].filter(Boolean) as string[]
}

// --- Components ---
const TX = ['SALE', 'RENT', 'LEASE'] as const
const PT = ['RESIDENTIAL', 'COMMERCIAL', 'PLOT', 'LAND'] as const
const PRICE_STATUS = ['EXACT', 'RANGE', 'CALL_FOR_PRICE', 'MARKET_PRICE'] as const
const FURNISHING = ['FULLY-FURNISHED', 'SEMI-FURNISHED', 'UNFURNISHED'] as const
const SORTS = [
  ['recent', 'Recent'],
  ['price_asc', 'Price ↑'],
  ['price_desc', 'Price ↓'],
  ['psf_asc', '₹/sqft ↑'],
  ['psf_desc', '₹/sqft ↓'],
] as const

const FilterSidebar = ({
  filters,
  onChange,
  onReset,
  facets,
}: {
  filters: ListingsQuery
  onChange: (next: ListingsQuery) => void
  onReset: () => void
  facets?: any
}) => {
  const set = <K extends keyof ListingsQuery>(key: K, value: ListingsQuery[K]) =>
    onChange({ ...filters, [key]: value, offset: 0 })

  const toggleArr = (key: keyof ListingsQuery, val: string) => {
    const current = (filters[key] as string[]) || []
    const next = current.includes(val) ? current.filter(x => x !== val) : [...current, val]
    set(key, next.length ? next : undefined)
  }

  const btnClass = (active: boolean) =>
    active
      ? 'border-cyan-500/40 bg-cyan-500/10 text-cyan-300 shadow-[0_0_10px_rgba(34,211,238,0.1)] border'
      : 'border-zinc-800 bg-zinc-950 text-zinc-400 hover:text-zinc-200 hover:bg-zinc-800 hover:border-zinc-700 border transition-all'

  return (
    <aside className='w-full shrink-0 md:w-72 md:sticky md:top-4 h-fit max-h-[calc(100vh-2rem)] overflow-y-auto rounded-2xl border border-zinc-800 bg-zinc-950 p-4 md:p-5 custom-scrollbar shadow-xl'>
      <div className='space-y-6'>
        <div>
          <p className='mb-2 text-[10px] font-bold uppercase tracking-widest text-zinc-500'>Semantic search</p>
          <Input
            placeholder='e.g. quiet 2 BHK near a park…'
            value={(filters.semantic_q as string) ?? ''}
            onChange={(e) => set('semantic_q', e.target.value)}
            className='bg-zinc-900 border-zinc-800 text-zinc-200 h-9 placeholder:text-zinc-600'
          />
          <p className='mt-1 text-[10px] font-medium text-zinc-500/70'>Ranks by embedding similarity.</p>
        </div>

        <div>
          <p className='mb-2 text-[10px] font-bold uppercase tracking-widest text-zinc-500'>Sort</p>
          <select
            className='h-9 w-full rounded-md border border-zinc-800 bg-zinc-900 px-3 text-sm font-medium text-zinc-200 outline-none focus:border-cyan-500/50 disabled:opacity-40 transition-colors'
            value={filters.sort_by ?? 'recent'}
            disabled={!!filters.semantic_q}
            onChange={(e) => set('sort_by', e.target.value as any)}
          >
            {SORTS.map(([value, label]) => (
              <option key={value} value={value}>{label}</option>
            ))}
          </select>
        </div>

        <div>
          <p className='mb-2 text-[10px] font-bold uppercase tracking-widest text-zinc-500'>Location</p>
          <select
            className='h-9 w-full rounded-md border border-zinc-800 bg-zinc-900 px-3 text-sm font-medium text-zinc-200 outline-none focus:border-cyan-500/50 transition-colors'
            value={(filters.canonical_location as string) ?? ''}
            onChange={(e) => set('canonical_location', e.target.value || undefined)}
          >
            <option value=''>Any location</option>
            {(facets?.canonical_location ?? []).map((bucket: any) => (
              <option key={bucket.value} value={bucket.value}>
                {bucket.value} ({bucket.count})
              </option>
            ))}
          </select>
        </div>

        <div>
          <p className='mb-2 text-[10px] font-bold uppercase tracking-widest text-zinc-500'>Transaction</p>
          <div className='grid grid-cols-2 gap-2'>
            {TX.map((val) => (
              <button
                key={val}
                className={`h-8 rounded-md px-2 text-[11px] font-semibold tracking-wide transition-all ${btnClass((filters.transaction_type || []).includes(val))}`}
                onClick={() => toggleArr('transaction_type', val)}
              >
                {val}
              </button>
            ))}
          </div>
        </div>

        <div>
          <p className='mb-2 text-[10px] font-bold uppercase tracking-widest text-zinc-500'>Property</p>
          <div className='grid grid-cols-2 gap-2'>
            {PT.map((val) => (
              <button
                key={val}
                className={`h-8 rounded-md px-2 text-[11px] font-semibold tracking-wide transition-all ${btnClass((filters.property_type || []).includes(val))}`}
                onClick={() => toggleArr('property_type', val)}
              >
                {val}
              </button>
            ))}
          </div>
        </div>

        <div>
          <p className='mb-2 text-[10px] font-bold uppercase tracking-widest text-zinc-500'>Price range (INR)</p>
          <div className='flex gap-2'>
            <Input
              type='number'
              placeholder='Min'
              value={(filters.min_price as number) ?? ''}
              onChange={(e) => set('min_price', e.target.value ? Number(e.target.value) : undefined)}
              className='bg-zinc-900 border-zinc-800 text-zinc-200 h-9 font-mono text-sm'
            />
            <Input
              type='number'
              placeholder='Max'
              value={(filters.max_price as number) ?? ''}
              onChange={(e) => set('max_price', e.target.value ? Number(e.target.value) : undefined)}
              className='bg-zinc-900 border-zinc-800 text-zinc-200 h-9 font-mono text-sm'
            />
          </div>
        </div>

        <div>
          <p className='mb-2 text-[10px] font-bold uppercase tracking-widest text-zinc-500'>₹ per sqft</p>
          <div className='flex gap-2'>
            <Input
              type='number'
              placeholder='Min'
              value={(filters.min_psf as number) ?? ''}
              onChange={(e) => set('min_psf', e.target.value ? Number(e.target.value) : undefined)}
              className='bg-zinc-900 border-zinc-800 text-zinc-200 h-9 font-mono text-sm'
            />
            <Input
              type='number'
              placeholder='Max'
              value={(filters.max_psf as number) ?? ''}
              onChange={(e) => set('max_psf', e.target.value ? Number(e.target.value) : undefined)}
              className='bg-zinc-900 border-zinc-800 text-zinc-200 h-9 font-mono text-sm'
            />
          </div>
        </div>

        <div>
          <p className='mb-2 text-[10px] font-bold uppercase tracking-widest text-zinc-500'>Price status</p>
          <div className='grid grid-cols-2 gap-2'>
            {PRICE_STATUS.map((val) => (
              <button
                key={val}
                className={`h-8 rounded-md px-2 text-[11px] font-semibold tracking-wide transition-all ${btnClass((filters.price_status || []).includes(val))}`}
                onClick={() => toggleArr('price_status', val)}
              >
                {humanize(val)}
              </button>
            ))}
          </div>
        </div>

        <div>
          <p className='mb-2 text-[10px] font-bold uppercase tracking-widest text-zinc-500'>Furnishing</p>
          <select
            className='h-9 w-full rounded-md border border-zinc-800 bg-zinc-900 px-3 text-sm font-medium text-zinc-200 outline-none focus:border-cyan-500/50 transition-colors'
            value={((filters.furnishing || [])[0] as string) ?? ''}
            onChange={(e) => set('furnishing', e.target.value ? [e.target.value] : undefined)}
          >
            <option value="">Any</option>
            {FURNISHING.map((val) => (
              <option key={val} value={val}>{humanize(val)}</option>
            ))}
          </select>
        </div>

        <div>
          <p className='mb-2 text-[10px] font-bold uppercase tracking-widest text-zinc-500'>More</p>
          <div className='grid grid-cols-2 gap-2'>
            <button
              className={`h-8 rounded-md px-2 text-[11px] font-semibold tracking-wide transition-all ${btnClass(filters.has_contact === true)}`}
              onClick={() => set('has_contact', filters.has_contact === true ? undefined : true)}
            >
              Has contact
            </button>
            <button
              className={`h-8 rounded-md px-2 text-[11px] font-semibold tracking-wide transition-all ${btnClass(filters.suspicious_only === true)}`}
              onClick={() => set('suspicious_only', filters.suspicious_only === true ? undefined : true)}
            >
              Needs review
            </button>
          </div>
        </div>

        <button 
          onClick={onReset} 
          className='w-full h-9 rounded-md text-[11px] font-bold uppercase tracking-widest text-zinc-500 hover:text-zinc-300 hover:bg-zinc-800 transition-colors'
        >
          Reset Filters
        </button>
      </div>
    </aside>
  )
}

const ListingCard = ({
  listing,
  onClick,
  selected = false,
  onSelectedChange,
}: {
  listing: ListingResult
  onClick?: () => void
  selected?: boolean
  onSelectedChange?: (checked: boolean) => void
}) => {
  const tone =
    listing.transaction_type === 'SALE'
      ? 'border-emerald-500/30 bg-emerald-500/10 text-emerald-300'
      : listing.transaction_type === 'RENT' || listing.transaction_type === 'LEASE'
      ? 'border-sky-500/30 bg-sky-500/10 text-sky-300'
      : 'border-zinc-500/30 bg-zinc-500/10 text-zinc-300'

  return (
    <Card
      className={`relative overflow-hidden cursor-pointer p-5 transition-all duration-300 hover:-tranzinc-y-1 hover:shadow-xl hover:shadow-cyan-900/10 border ${selected ? 'border-cyan-500/50 bg-cyan-950/20' : 'border-zinc-800 bg-zinc-950 hover:border-cyan-500/30'}`}
      onClick={onClick}
    >
      <div className='flex flex-wrap items-start justify-between gap-3'>
        <div className='flex gap-3 min-w-0 flex-1'>
          {onSelectedChange && (
            <input
              type='checkbox'
              checked={selected}
              onChange={(event) => onSelectedChange(event.currentTarget.checked)}
              onClick={(event) => event.stopPropagation()}
              className='mt-1.5 h-4 w-4 shrink-0 rounded border-zinc-600 bg-zinc-950 text-cyan-500 focus:ring-cyan-500/40 focus:ring-offset-zinc-900 transition'
            />
          )}
          <div className='min-w-0 flex-1'>
            <div className='flex items-center gap-2 mb-1.5'>
              <span className='text-[10px] font-bold uppercase tracking-widest text-zinc-500'>
                {listing.property_type}
              </span>
              <span className='h-1 w-1 rounded-full bg-zinc-700'></span>
              <button
                type='button'
                onClick={(event) => {
                  event.stopPropagation()
                  void navigator.clipboard?.writeText(String(listing.id))
                  toast.success('Listing ID copied to clipboard')
                }}
                className='font-mono text-[10px] tracking-tight text-zinc-500 hover:text-cyan-400 transition'
              >
                #{listing.id.slice(0, 8)}
              </button>
            </div>
            
            <h3 className='text-base font-semibold tracking-tight text-zinc-200 flex items-start gap-1.5'>
              <span className='min-w-0 break-words'>{listingTitle(listing)}</span>
            </h3>
            
            {listing.canonical_location && (
              <p className='flex min-w-0 items-center gap-1.5 mt-1 text-sm text-zinc-400 font-medium'>
                <MapPin className='h-3.5 w-3.5 shrink-0 text-cyan-500/70' />
                <span className='min-w-0 truncate'>{listing.canonical_location}</span>
              </p>
            )}
          </div>
        </div>

        <div className='flex flex-col items-end gap-2 shrink-0'>
          <Badge className={`${tone} px-2.5 py-0.5 text-[10px] font-bold tracking-widest border uppercase`}>
            {listing.transaction_type}
          </Badge>
          {listing.listing_intent === 'REQUEST' && (
            <span className='rounded border border-amber-500/40 bg-amber-500/10 px-2 py-0.5 text-[10px] font-bold text-amber-200 tracking-wider uppercase'>
              Requirement
            </span>
          )}
        </div>
      </div>

      <div className='mt-5 grid grid-cols-3 gap-4 border-t border-zinc-800 pt-4'>
        <div className='space-y-1'>
          <p className='flex items-center gap-1.5 text-[10px] font-bold uppercase tracking-wider text-zinc-500'>
            <BedDouble className='h-3.5 w-3.5' /> BHK
          </p>
          <p className='text-sm font-semibold text-zinc-300'>{listing.bhk ?? '—'}</p>
        </div>
        <div className='space-y-1'>
          <p className='flex items-center gap-1.5 text-[10px] font-bold uppercase tracking-wider text-zinc-500'>
            <Ruler className='h-3.5 w-3.5' /> SqFt
          </p>
          <p className='text-sm font-semibold text-zinc-300'>{listing.sqft ?? '—'}</p>
        </div>
        <div className='space-y-1'>
          <p className='flex items-center gap-1.5 text-[10px] font-bold uppercase tracking-wider text-zinc-500'>
            <IndianRupee className='h-3.5 w-3.5' /> Price
          </p>
          <div className='leading-tight'>
            {(() => {
              const psf = perSqftSummary(listing)
              if (psf?.kind === 'rate_only') {
                return (
                  <>
                    <p className='text-sm font-semibold text-cyan-400'>{formatPricePerSqft(psf.rate)}</p>
                    <p className='text-[10px] text-amber-400 mt-0.5'>Rate only</p>
                  </>
                )
              }
              return (
                <>
                  <p className='text-sm font-semibold text-cyan-400'>
                    {formatPriceRange(listing.price_min, listing.price_max, listing.price_status)}
                  </p>
                  {psf?.kind === 'converted' && (
                    <p className='text-[10px] font-medium text-zinc-500 mt-0.5'>
                      {formatPricePerSqft(psf.rate)}
                    </p>
                  )}
                </>
              )
            })()}
          </div>
        </div>
      </div>

      <div className='mt-5 flex flex-wrap gap-1.5'>
        {compactFacts(listing).slice(0, 5).map((f) => (
          <span key={String(f)} className='rounded-md border border-zinc-800 bg-zinc-900 px-2.5 py-1 text-[10px] font-medium tracking-wide text-zinc-400'>
            {f}
          </span>
        ))}
      </div>

      {listing.suspicious_flags.length > 0 && (
        <div className='mt-3 flex items-center gap-2 rounded-lg border border-amber-500/20 bg-amber-500/5 px-3 py-2 text-xs font-medium text-amber-300/90'>
          <AlertTriangle className='h-3.5 w-3.5 shrink-0' />
          <span className='truncate'>Review: {listing.suspicious_flags.slice(0, 2).map(humanize).join(', ')}</span>
        </div>
      )}
    </Card>
  )
}

function ListingListRow({
  listing,
  onClick,
  selected,
  onSelectedChange,
}: {
  listing: ListingResult
  onClick: () => void
  selected: boolean
  onSelectedChange: (checked: boolean) => void
}) {
  return (
    <button
      type='button'
      onClick={onClick}
      className={`grid w-full gap-4 rounded-xl border p-4 text-left transition-all duration-300 md:grid-cols-[auto_1.4fr_0.9fr_0.8fr_1.2fr] ${selected ? 'border-cyan-500/50 bg-cyan-950/20 shadow-lg shadow-cyan-900/10' : 'border-zinc-800 bg-zinc-950 hover:border-cyan-500/30'}`}
    >
      <input
        type='checkbox'
        checked={selected}
        onChange={(event) => onSelectedChange(event.currentTarget.checked)}
        onClick={(event) => event.stopPropagation()}
        aria-label={`Select ${listingTitle(listing)}`}
        className='mt-1.5 h-4 w-4 rounded border-zinc-600 bg-zinc-950 text-cyan-500 focus:ring-cyan-500/40 focus:ring-offset-zinc-900 transition'
      />
      <div>
        <div className='flex flex-wrap items-center gap-2 mb-1'>
          <p className='text-sm font-semibold tracking-tight text-zinc-200'>
            {listingTitle(listing)}
          </p>
          <span className='rounded border border-zinc-800 bg-zinc-900 px-1.5 py-0.5 text-[9px] font-bold uppercase tracking-widest text-zinc-400'>
            {listing.transaction_type}
          </span>
          {listing.listing_intent === 'REQUEST' && (
            <span className='rounded border border-amber-500/30 bg-amber-500/10 px-1.5 py-0.5 text-[9px] font-bold uppercase tracking-widest text-amber-300'>
              Req
            </span>
          )}
        </div>
        <p className='text-xs font-medium text-zinc-500'>{listing.canonical_location || listing.location || 'Unknown area'}</p>
      </div>
      <div>
        <p className='text-[10px] font-bold uppercase tracking-widest text-zinc-500 mb-0.5'>Specs</p>
        <p className='text-sm font-semibold text-zinc-300'>
          {listing.bhk ?? '—'} BHK · {listing.sqft ?? '—'} sqft
        </p>
      </div>
      <div>
        <p className='text-[10px] font-bold uppercase tracking-widest text-zinc-500 mb-0.5'>Price</p>
        <div className='leading-tight'>
          {(() => {
            const psf = perSqftSummary(listing)
            if (psf?.kind === 'rate_only') {
              return (
                <>
                  <p className='text-sm font-semibold text-cyan-400'>{formatPricePerSqft(psf.rate)}</p>
                  <p className='text-[10px] text-amber-400 mt-0.5'>Rate only</p>
                </>
              )
            }
            return (
              <>
                <p className='text-sm font-semibold text-cyan-400'>
                  {formatPriceRange(listing.price_min, listing.price_max, listing.price_status)}
                </p>
                {psf?.kind === 'converted' && (
                  <p className='text-[10px] font-medium text-zinc-500 mt-0.5'>
                    {formatPricePerSqft(psf.rate)}
                  </p>
                )}
              </>
            )
          })()}
        </div>
      </div>
      <div className='flex flex-wrap content-start gap-1.5 mt-1'>
        {compactFacts(listing).slice(0, 4).map((fact) => (
          <span key={fact} className='rounded-md border border-zinc-800 bg-zinc-900 px-2 py-1 text-[9px] font-bold uppercase tracking-widest text-zinc-400'>
            {fact}
          </span>
        ))}
      </div>
    </button>
  )
}

function ListingsTable({
  listings,
  selectedIds,
  onToggleOne,
  onToggleAll,
  allSelected,
  someSelected,
  onSelect,
}: {
  listings: ListingResult[]
  selectedIds: Set<string>
  onToggleOne: (id: string, checked: boolean) => void
  onToggleAll: (checked: boolean) => void
  allSelected: boolean
  someSelected: boolean
  onSelect: (id: string) => void
}) {
  return (
    <div className='overflow-x-auto rounded-xl border border-zinc-800 bg-zinc-950 shadow-xl'>
      <table className='w-full min-w-[980px] border-collapse text-left text-sm'>
        <thead className='bg-zinc-950 text-[10px] font-bold uppercase tracking-widest text-zinc-500 border-b border-zinc-800'>
          <tr>
            <th className='px-4 py-4 w-12'>
              <input
                type='checkbox'
                checked={allSelected}
                ref={(el) => {
                  if (el) el.indeterminate = someSelected && !allSelected
                }}
                onChange={(event) => onToggleAll(event.currentTarget.checked)}
                aria-label='Select all listings on this page'
                className='h-4 w-4 rounded border-zinc-600 bg-zinc-950 text-cyan-500 focus:ring-cyan-500/40 transition'
              />
            </th>
            <th className='px-4 py-4'>Property</th>
            <th className='px-4 py-4'>Intent</th>
            <th className='px-4 py-4'>BHK</th>
            <th className='px-4 py-4'>Area</th>
            <th className='px-4 py-4'>Price</th>
            <th className='px-4 py-4'>₹/sqft</th>
            <th className='px-4 py-4'>Source</th>
            <th className='px-4 py-4 text-right'>Review</th>
          </tr>
        </thead>
        <tbody className='divide-y divide-zinc-800'>
          {listings.map((l) => (
            <tr key={l.id} className='cursor-pointer bg-transparent transition-colors hover:bg-zinc-800 group' onClick={() => onSelect(l.id)}>
              <td className='px-4 py-3'>
                <input
                  type='checkbox'
                  checked={selectedIds.has(l.id)}
                  onChange={(event) => onToggleOne(l.id, event.currentTarget.checked)}
                  onClick={(event) => event.stopPropagation()}
                  aria-label={`Select ${listingTitle(l)}`}
                  className='h-4 w-4 rounded border-zinc-600 bg-zinc-950 text-cyan-500 focus:ring-cyan-500/40 transition'
                />
              </td>
              <td className='px-4 py-3'>
                <p className='font-semibold tracking-tight text-zinc-200 group-hover:text-cyan-400 transition-colors'>{listingTitle(l)}</p>
                <p className='text-xs font-medium text-zinc-500 mt-0.5'>{l.canonical_location || l.location || '—'}</p>
              </td>
              <td className='px-4 py-3 text-xs font-semibold text-zinc-400'>{l.listing_intent === 'REQUEST' ? 'REQ' : l.transaction_type}</td>
              <td className='px-4 py-3 text-sm font-semibold text-zinc-300'>{l.bhk ?? '—'}</td>
              <td className='px-4 py-3 text-sm font-semibold text-zinc-300'>{l.sqft ?? '—'}</td>
              <td className='px-4 py-3'>
                {(() => {
                  const psf = perSqftSummary(l)
                  if (psf?.kind === 'rate_only') {
                    return (
                      <>
                        <p className='font-semibold text-cyan-400'>{formatPricePerSqft(psf.rate)}</p>
                        <p className='text-[10px] font-medium text-amber-500 mt-0.5'>Rate only</p>
                      </>
                    )
                  }
                  return <p className='font-semibold text-zinc-300'>{formatPriceRange(l.price_min, l.price_max, l.price_status)}</p>
                })()}
              </td>
              <td className='px-4 py-3 text-xs font-medium text-zinc-500'>
                {l.price_per_sqft != null ? formatPricePerSqft(l.price_per_sqft) : '—'}
              </td>
              <td className='px-4 py-3 text-xs font-medium text-zinc-500 truncate max-w-[120px]'>{l.sender || '—'}</td>
              <td className='px-4 py-3 text-right'>
                {l.suspicious_flags.length ? (
                  <span className='inline-flex items-center justify-center h-6 w-6 rounded-full bg-amber-500/10 border border-amber-500/20 text-xs font-bold text-amber-400'>
                    {l.suspicious_flags.length}
                  </span>
                ) : '—'}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

const ListingDetailModal = ({
  listing,
  open,
  onOpenChange
}: {
  listing?: ListingResult
  open: boolean
  onOpenChange: (val: boolean) => void
}) => {
  const sourceQuery = useSourceQuery(listing?.id, open)
  if (!listing) return null
  
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className='max-w-3xl max-h-[90vh] overflow-y-auto bg-zinc-950 border border-zinc-800 text-zinc-200 shadow-2xl custom-scrollbar'>
        <DialogHeader className='border-b border-zinc-800 pb-4 mb-4'>
          <DialogTitle className='text-xl font-semibold tracking-tight flex items-center gap-2'>
            <span className='h-2 w-2 rounded-full bg-cyan-500'></span>
            Listing Details
          </DialogTitle>
        </DialogHeader>
        <div className='space-y-6'>
          <div className='flex items-start justify-between gap-4'>
            <div>
              <p className='text-[10px] font-bold uppercase tracking-widest text-cyan-500 mb-1'>
                {listing.property_type} • {listing.transaction_type}
              </p>
              <h2 className='text-2xl font-bold tracking-tight text-zinc-100'>
                {listing.canonical_location || listing.location}
              </h2>
            </div>
            <div className='text-right'>
              <p className='text-[10px] font-bold uppercase tracking-widest text-zinc-500 mb-1'>Price</p>
              <div className='text-2xl font-bold text-cyan-400'>
                {(() => {
                  const psf = perSqftSummary(listing)
                  if (psf?.kind === 'rate_only') return formatPricePerSqft(psf.rate)
                  return formatPriceRange(listing.price_min, listing.price_max, listing.price_status)
                })()}
              </div>
            </div>
          </div>

          <div className='grid grid-cols-2 md:grid-cols-4 gap-4 p-4 rounded-xl bg-zinc-900 border border-zinc-800'>
            <div>
              <p className='text-[10px] font-bold uppercase tracking-widest text-zinc-500 mb-1'>BHK</p>
              <p className='text-lg font-semibold text-zinc-200'>{listing.bhk ?? '—'}</p>
            </div>
            <div>
              <p className='text-[10px] font-bold uppercase tracking-widest text-zinc-500 mb-1'>Area</p>
              <p className='text-lg font-semibold text-zinc-200'>{listing.sqft ?? '—'} <span className='text-xs font-normal text-zinc-500'>sqft</span></p>
            </div>
            <div>
              <p className='text-[10px] font-bold uppercase tracking-widest text-zinc-500 mb-1'>Furnishing</p>
              <p className='text-sm font-semibold text-zinc-200 mt-1'>{humanize(listing.furnishing) || '—'}</p>
            </div>
            <div>
              <p className='text-[10px] font-bold uppercase tracking-widest text-zinc-500 mb-1'>Floor</p>
              <p className='text-sm font-semibold text-zinc-200 mt-1'>{humanize(listing.floor_band) || '—'}</p>
            </div>
          </div>

          <div className='grid grid-cols-2 md:grid-cols-4 gap-4'>
            <div className='p-4 rounded-xl bg-zinc-900 border border-zinc-800'>
              <p className='text-[10px] font-bold uppercase tracking-widest text-zinc-500 mb-1'>Pets</p>
              <p className='text-sm font-semibold text-zinc-300'>{listing.pets_allowed === true ? 'Allowed' : listing.pets_allowed === false ? 'No pets' : '—'}</p>
            </div>
            <div className='p-4 rounded-xl bg-zinc-900 border border-zinc-800'>
              <p className='text-[10px] font-bold uppercase tracking-widest text-zinc-500 mb-1'>Contact</p>
              <p className='text-sm font-semibold text-zinc-300'>{listing.has_contact ? 'Available' : 'None'}</p>
            </div>
            <div className='p-4 rounded-xl bg-zinc-900 border border-zinc-800'>
              <p className='text-[10px] font-bold uppercase tracking-widest text-zinc-500 mb-1'>Confidence</p>
              <p className='text-sm font-semibold text-zinc-300'>{listing.confidence_score == null ? '—' : `${Math.round(listing.confidence_score * 100)}%`}</p>
            </div>
            <div className='p-4 rounded-xl bg-zinc-900 border border-zinc-800'>
              <p className='text-[10px] font-bold uppercase tracking-widest text-zinc-500 mb-1'>Timestamp</p>
              <p className='text-sm font-semibold text-zinc-300'>{listing.timestamp ? format(new Date(listing.timestamp), 'PP') : '—'}</p>
            </div>
          </div>

          {listing.suspicious_flags.length > 0 && (
            <div className='rounded-xl border border-amber-500/20 bg-amber-500/5 p-4 flex gap-3'>
              <AlertTriangle className='h-5 w-5 shrink-0 text-amber-500 mt-0.5' />
              <div>
                <p className='text-sm font-bold text-amber-500 mb-1'>Needs Review</p>
                <p className='text-sm text-amber-200/80'>{listing.suspicious_flags.map(humanize).join(' • ')}</p>
              </div>
            </div>
          )}

          <div className='mt-8 pt-6 border-t border-zinc-800'>
            <h3 className='text-sm font-bold uppercase tracking-widest text-zinc-500 mb-4'>Source Context</h3>
            {sourceQuery.isLoading ? (
              <div className='flex items-center gap-3 p-6 rounded-xl border border-zinc-800 bg-zinc-900 text-sm font-medium text-zinc-400'>
                <Loader2 className='h-5 w-5 animate-spin text-cyan-500' /> Fetching raw message…
              </div>
            ) : sourceQuery.data ? (
              <div className='rounded-xl border border-zinc-800 bg-zinc-900 shadow-inner overflow-hidden'>
                <div className='flex flex-wrap items-center justify-between gap-2 border-b border-zinc-800 bg-zinc-950 px-5 py-3'>
                  <div>
                    <p className='text-[10px] font-bold uppercase tracking-widest text-zinc-500 mb-0.5'>Sender</p>
                    <p className='text-sm font-semibold text-cyan-300'>{sourceQuery.data.sender || listing.sender || 'Unknown sender'}</p>
                  </div>
                  {sourceQuery.data.created_at && (
                    <div className='text-right'>
                      <p className='text-[10px] font-bold uppercase tracking-widest text-zinc-500 mb-0.5'>Received</p>
                      <p className='text-xs font-medium text-zinc-400'>{format(new Date(sourceQuery.data.created_at), 'PPp')}</p>
                    </div>
                  )}
                </div>
                <div className='p-5'>
                  <p className='whitespace-pre-wrap break-words text-[13px] leading-relaxed text-zinc-300 font-medium'>
                    {sourceQuery.data.raw_text}
                  </p>
                </div>
              </div>
            ) : (
              <p className='text-sm text-zinc-500 italic'>No source context found for this listing.</p>
            )}
          </div>
        </div>
      </DialogContent>
    </Dialog>
  )
}

// --- Main Page ---
const DEFAULT_FILTERS: ListingsQuery = { limit: 50, offset: 0, sort_by: 'recent' }
type ViewMode = 'cards' | 'list' | 'table'

export const SearchPage = () => {
  const [filters, setFilters] = useState<ListingsQuery>(DEFAULT_FILTERS)
  const [activeId, setActiveId] = useState<string | undefined>()
  const [viewMode, setViewMode] = useState<ViewMode>('cards')
  const [selectedIds, setSelectedIds] = useState<Set<string>>(() => new Set())

  const listingsQuery = useListingsQuery(filters)
  const facetsQuery = useFacetsQuery()
  const deleteMutation = useDeleteListingsMutation()
  
  const listings = listingsQuery.data?.items ?? []
  const pageIds = useMemo(() => listings.map((listing) => listing.id), [listings])
  const selectedCount = selectedIds.size
  const allPageSelected = pageIds.length > 0 && pageIds.every((id) => selectedIds.has(id))
  const somePageSelected = pageIds.some((id) => selectedIds.has(id))

  const page = Math.floor((filters.offset ?? 0) / (filters.limit ?? 50)) + 1
  const total = listingsQuery.data?.total ?? 0
  const numPages = Math.ceil(total / (filters.limit ?? 50)) || 1
  const canPrev = page > 1
  const canNext = page < numPages

  const toggleOne = (id: string, checked: boolean) => {
    setSelectedIds((prev) => {
      const next = new Set(prev)
      if (checked) next.add(id)
      else next.delete(id)
      return next
    })
  }

  const togglePage = (checked: boolean) => {
    setSelectedIds((prev) => {
      const next = new Set(prev)
      pageIds.forEach((id) => {
        if (checked) next.add(id)
        else next.delete(id)
      })
      return next
    })
  }

  const deleteSelected = async () => {
    const ids = Array.from(selectedIds)
    if (!ids.length) return
    if (!window.confirm(`Delete ${ids.length} selected listing${ids.length === 1 ? '' : 's'}?`)) return
    try {
      const result = await deleteMutation.mutateAsync(ids)
      setSelectedIds((prev) => {
        const next = new Set(prev)
        ids.forEach((id) => next.delete(id))
        return next
      })
      if (activeId && ids.includes(activeId)) setActiveId(undefined)
      toast.success(`Deleted ${result.deleted} listing${result.deleted === 1 ? '' : 's'}.`)
    } catch {
      toast.error('Could not delete selected listings.')
    }
  }

  const handleExport = () => {
    const dataToExport = selectedCount > 0 
      ? listings.filter((l) => selectedIds.has(l.id))
      : listings;
    
    if (dataToExport.length === 0) return;

    const headers = ['ID', 'Transaction', 'Property', 'Location', 'Price', 'BHK', 'Sqft', 'Sender'];
    const rows = dataToExport.map(listing => [
      listing.id,
      listing.transaction_type,
      listing.property_type,
      listing.location || '',
      listing.price || listing.price_max || listing.price_min || 0,
      listing.bhk || '',
      listing.sqft || '',
      listing.sender || ''
    ]);
    
    const csvContent = [
      headers.join(','),
      ...rows.map(row => row.map(cell => `"${String(cell).replace(/"/g, '""')}"`).join(','))
    ].join('\n');

    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.setAttribute('href', url);
    link.setAttribute('download', 'listings_export.csv');
    link.style.visibility = 'hidden';
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  }

  return (
    <section className='flex min-h-[calc(100vh-140px)] flex-col gap-6 md:flex-row pb-12'>
      <FilterSidebar
        filters={filters}
        onChange={setFilters}
        onReset={() => setFilters(DEFAULT_FILTERS)}
        facets={facetsQuery.data}
      />

      <div className='flex-1 space-y-6'>
        <div className='flex flex-wrap items-center justify-between gap-4 border-b border-zinc-800 pb-4'>
          <div>
            <h1 className='text-3xl font-bold tracking-tight text-zinc-100 mb-1'>Listings</h1>
            <p className='text-sm font-medium text-zinc-500'>
              <span className='text-cyan-400'>{total.toLocaleString('en-IN')}</span> active records in the index
            </p>
          </div>
          <div className='flex flex-wrap items-center gap-3 text-sm'>
            <div className='flex rounded-lg border border-zinc-800 bg-zinc-900 p-1 shadow-inner'>
              {[
                ['cards', LayoutGrid],
                ['list', List],
                ['table', Table2],
              ].map(([mode, Icon]) => {
                const isActive = viewMode === mode
                return (
                  <button
                    key={mode as string}
                    onClick={() => setViewMode(mode as ViewMode)}
                    aria-label={`${mode} view`}
                    className={`flex h-8 w-10 items-center justify-center rounded-md transition-all ${
                      isActive 
                        ? 'bg-cyan-500/20 text-cyan-400 shadow-[0_0_10px_rgba(34,211,238,0.1)]' 
                        : 'text-zinc-500 hover:bg-zinc-800 hover:text-zinc-300'
                    }`}
                  >
                    <Icon className='h-4 w-4' />
                  </button>
                )
              })}
            </div>
          </div>
        </div>

        <div className='flex flex-wrap items-center justify-between gap-4 rounded-2xl border border-zinc-800 bg-zinc-950 px-5 py-3 shadow-sm'>
          <label className='flex items-center gap-3 cursor-pointer group'>
            <input
              type='checkbox'
              checked={allPageSelected}
              ref={(el) => {
                if (el) el.indeterminate = somePageSelected && !allPageSelected
              }}
              onChange={(event) => togglePage(event.currentTarget.checked)}
              className='h-4 w-4 rounded border-zinc-600 bg-zinc-950 text-cyan-500 focus:ring-cyan-500/40 transition'
            />
            <span className='text-xs font-bold uppercase tracking-widest text-zinc-400 group-hover:text-zinc-300 transition-colors'>
              Select Page
            </span>
          </label>
          <div className='flex items-center gap-2'>
            {selectedCount ? (
              <Button size='sm' variant='ghost' onClick={() => setSelectedIds(new Set())} className='text-zinc-400 hover:text-zinc-100'>
                Clear ({selectedCount})
              </Button>
            ) : null}
            <Button
              size='sm'
              variant='outline'
              className='border-zinc-800 bg-zinc-950 hover:bg-zinc-900 hover:text-zinc-100'
              disabled={listings.length === 0}
              onClick={handleExport}
            >
              <Download className='mr-2 h-3.5 w-3.5' />
              Export {selectedCount > 0 ? 'Selected' : 'All'}
            </Button>
            <Button
              size='sm'
              variant='destructive'
              className='bg-red-500/10 text-red-400 hover:bg-red-500/20 hover:text-red-300 border border-red-500/20'
              disabled={!selectedCount || deleteMutation.isPending}
              onClick={deleteSelected}
            >
              {deleteMutation.isPending ? <Loader2 className='mr-2 h-3.5 w-3.5 animate-spin' /> : <Trash2 className='mr-2 h-3.5 w-3.5' />}
              Delete ({selectedCount})
            </Button>
          </div>
        </div>

        {listingsQuery.isLoading ? (
          <div className='flex flex-col items-center justify-center py-20 text-zinc-400'>
            <Loader2 className='h-8 w-8 animate-spin text-cyan-500 mb-4' /> 
            <p className='text-sm font-medium tracking-wide'>Fetching listings database…</p>
          </div>
        ) : listingsQuery.isError ? (
          <Card className='flex items-center gap-3 border-red-500/30 bg-red-500/10 p-5 text-sm font-medium text-red-300 rounded-2xl'>
            <AlertTriangle className='h-5 w-5' /> Failed to retrieve records. Check server connection.
          </Card>
        ) : listings.length === 0 ? (
          <Card className='flex flex-col items-center justify-center py-20 text-center border-zinc-800 bg-zinc-950 rounded-2xl border-dashed'>
            <SearchIcon className='h-10 w-10 text-zinc-600 mb-4' />
            <p className='text-base font-semibold text-zinc-300 mb-1'>No results found</p>
            <p className='text-sm text-zinc-500'>Adjust your filters or semantic search to broaden your query.</p>
          </Card>
        ) : viewMode === 'table' ? (
          <ListingsTable
            listings={listings}
            selectedIds={selectedIds}
            onToggleOne={toggleOne}
            onToggleAll={togglePage}
            allSelected={allPageSelected}
            someSelected={somePageSelected}
            onSelect={setActiveId}
          />
        ) : viewMode === 'list' ? (
          <div className='space-y-4'>
            {listings.map((l) => (
              <ListingListRow
                key={l.id}
                listing={l}
                selected={selectedIds.has(l.id)}
                onSelectedChange={(checked) => toggleOne(l.id, checked)}
                onClick={() => setActiveId(l.id)}
              />
            ))}
          </div>
        ) : (
          <div className='grid gap-5 md:grid-cols-2 xl:grid-cols-3'>
            {listings.map((l) => (
              <ListingCard
                key={l.id}
                listing={l}
                selected={selectedIds.has(l.id)}
                onSelectedChange={(checked) => toggleOne(l.id, checked)}
                onClick={() => setActiveId(l.id)}
              />
            ))}
          </div>
        )}

        {!listingsQuery.isLoading && !listingsQuery.isError && listings.length > 0 && numPages > 1 ? (
          <div className='flex flex-wrap items-center justify-between gap-4 rounded-2xl border border-zinc-800 bg-zinc-950 px-5 py-4'>
            <span className='text-xs font-bold uppercase tracking-widest text-zinc-500'>
              Records {(filters.offset ?? 0) + 1}–{Math.min((filters.offset ?? 0) + (filters.limit ?? 50), total)} of {total}
            </span>
            <div className='flex items-center gap-1.5'>
              <Button size='sm' variant='outline' className='h-8 border-zinc-800 bg-zinc-950 text-zinc-300 hover:text-zinc-100' disabled={!canPrev} onClick={() => setFilters({ ...filters, offset: 0 })}>
                First
              </Button>
              <Button size='sm' variant='outline' className='h-8 border-zinc-800 bg-zinc-950 text-zinc-300 hover:text-zinc-100' disabled={!canPrev} onClick={() => setFilters({ ...filters, offset: (filters.offset ?? 0) - (filters.limit ?? 50) })}>
                Prev
              </Button>
              <span className='mx-3 text-xs font-bold tracking-widest text-zinc-500 uppercase'>
                <span className='text-cyan-400'>{page}</span> / {numPages}
              </span>
              <Button size='sm' variant='outline' className='h-8 border-zinc-800 bg-zinc-950 text-zinc-300 hover:text-zinc-100' disabled={!canNext} onClick={() => setFilters({ ...filters, offset: (filters.offset ?? 0) + (filters.limit ?? 50) })}>
                Next
              </Button>
              <Button size='sm' variant='outline' className='h-8 border-zinc-800 bg-zinc-950 text-zinc-300 hover:text-zinc-100' disabled={!canNext} onClick={() => setFilters({ ...filters, offset: (numPages - 1) * (filters.limit ?? 50) })}>
                Last
              </Button>
            </div>
          </div>
        ) : null}
      </div>

      <ListingDetailModal 
        listing={listings.find(l => l.id === activeId)}
        open={Boolean(activeId)}
        onOpenChange={(open) => !open && setActiveId(undefined)}
      />
    </section>
  )
}

function SearchIcon(props: React.SVGProps<SVGSVGElement>) {
  return (
    <svg
      {...props}
      xmlns="http://www.w3.org/2000/svg"
      width="24"
      height="24"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <circle cx="11" cy="11" r="8" />
      <path d="m21 21-4.3-4.3" />
    </svg>
  )
}





