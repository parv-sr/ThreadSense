import { useMemo, useState } from 'react'
import type { ReactNode } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { ChevronLeft, ChevronRight, Search, Trash2 } from 'lucide-react'
import { toast } from 'sonner'
import { SourceViewerModal } from '@/components/modals/source-viewer-modal'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { useDeleteListingsMutation, useFacetsQuery, useListingsQuery, useSourceQuery } from '@/lib/api'
import type { ListingResult, ListingsQuery } from '@/types/api'

const LIMIT = 50
const TRANSACTIONS = ['RENT', 'SALE', 'LEASE']
const PROPERTY_TYPES = ['RESIDENTIAL', 'COMMERCIAL', 'PLOT', 'LAND']
const FURNISHING = ['FULLY-FURNISHED', 'SEMI-FURNISHED', 'UNFURNISHED']
const BHK_OPTIONS = [1, 2, 3, 4]

const formatPrice = (listing: ListingResult) => {
  const value = listing.price ?? listing.price_max ?? listing.price_min
  if (!value) return listing.price_status.replaceAll('_', ' ')
  return new Intl.NumberFormat('en-IN', {
    style: 'currency',
    currency: 'INR',
    maximumFractionDigits: 0,
  }).format(value)
}

const toggle = <T,>(items: T[], value: T) =>
  items.includes(value) ? items.filter((item) => item !== value) : [...items, value]

export const SearchPage = () => {
  const queryClient = useQueryClient()
  const [semantic, setSemantic] = useState('')
  const [location, setLocation] = useState('')
  const [transactionTypes, setTransactionTypes] = useState<string[]>([])
  const [propertyTypes, setPropertyTypes] = useState<string[]>([])
  const [furnishing, setFurnishing] = useState<string[]>([])
  const [bhk, setBhk] = useState<number[]>([])
  const [minPrice, setMinPrice] = useState<number | ''>('')
  const [maxPrice, setMaxPrice] = useState<number | ''>('')
  const [offset, setOffset] = useState(0)
  const [selected, setSelected] = useState<string[]>([])
  const [openSource, setOpenSource] = useState(false)
  const [activeListingId, setActiveListingId] = useState<string>()

  const query: ListingsQuery = useMemo(
    () => ({
      transaction_type: transactionTypes,
      property_type: propertyTypes,
      furnishing,
      bhk,
      canonical_location: location.trim().toLowerCase() || undefined,
      min_price: minPrice,
      max_price: maxPrice,
      semantic_q: semantic.trim() || undefined,
      limit: LIMIT,
      offset,
    }),
    [bhk, furnishing, location, maxPrice, minPrice, offset, propertyTypes, semantic, transactionTypes],
  )

  const facetsQuery = useFacetsQuery()
  const listingsQuery = useListingsQuery(query)
  const deleteMutation = useDeleteListingsMutation()
  const sourceQuery = useSourceQuery(activeListingId, openSource)

  const listings = listingsQuery.data?.items ?? []
  const total = listingsQuery.data?.total ?? 0
  const allVisibleSelected = listings.length > 0 && listings.every((item) => selected.includes(item.id))

  const resetPaging = () => {
    setOffset(0)
    setSelected([])
  }

  const deleteSelected = async () => {
    if (selected.length === 0) return
    const result = await deleteMutation.mutateAsync(selected)
    toast.success(`Deleted ${result.deleted} listing${result.deleted === 1 ? '' : 's'}.`)
    setSelected([])
    await queryClient.invalidateQueries({ queryKey: ['listings'] })
    await queryClient.invalidateQueries({ queryKey: ['listing-facets'] })
  }

  return (
    <section className='flex h-[calc(100vh-88px)] min-h-[680px] flex-col gap-4'>
      <div className='flex flex-wrap items-center justify-between gap-3 border-b border-zinc-800 pb-4'>
        <div>
          <h1 className='text-2xl font-semibold'>Search</h1>
          <p className='text-sm text-zinc-500'>{total.toLocaleString('en-IN')} listings in the current result set</p>
        </div>
        <div className='flex min-w-[280px] flex-1 items-center gap-2 md:max-w-2xl'>
          <Search className='h-4 w-4 text-zinc-500' />
          <Input
            value={semantic}
            onChange={(event) => {
              setSemantic(event.target.value)
              resetPaging()
            }}
            placeholder='Semantic overlay within filtered results'
          />
        </div>
      </div>

      <div className='grid min-h-0 flex-1 grid-cols-1 gap-4 lg:grid-cols-[290px_1fr]'>
        <aside className='min-h-0 overflow-auto border border-zinc-800 bg-zinc-950 p-4'>
          <div className='space-y-5'>
            <label className='block space-y-2'>
              <span className='text-xs font-medium uppercase text-zinc-500'>Canonical Location</span>
              <Input
                value={location}
                onChange={(event) => {
                  setLocation(event.target.value)
                  resetPaging()
                }}
                list='locations'
                placeholder='bandra west'
              />
              <datalist id='locations'>
                {facetsQuery.data?.canonical_location?.map((bucket) => (
                  <option key={bucket.value} value={bucket.value} />
                ))}
              </datalist>
            </label>

            <div className='grid grid-cols-2 gap-2'>
              <label className='space-y-2'>
                <span className='text-xs font-medium uppercase text-zinc-500'>Min Price</span>
                <Input
                  type='number'
                  min={0}
                  value={minPrice}
                  onChange={(event) => {
                    setMinPrice(event.target.value ? Number(event.target.value) : '')
                    resetPaging()
                  }}
                />
              </label>
              <label className='space-y-2'>
                <span className='text-xs font-medium uppercase text-zinc-500'>Max Price</span>
                <Input
                  type='number'
                  min={0}
                  value={maxPrice}
                  onChange={(event) => {
                    setMaxPrice(event.target.value ? Number(event.target.value) : '')
                    resetPaging()
                  }}
                />
              </label>
            </div>

            <FilterGroup title='Transaction'>
              {TRANSACTIONS.map((item) => (
                <CheckLine
                  key={item}
                  label={item}
                  checked={transactionTypes.includes(item)}
                  count={facetsQuery.data?.transaction_type?.find((bucket) => bucket.value === item)?.count}
                  onChange={() => {
                    setTransactionTypes((current) => toggle(current, item))
                    resetPaging()
                  }}
                />
              ))}
            </FilterGroup>

            <FilterGroup title='Property'>
              {PROPERTY_TYPES.map((item) => (
                <CheckLine
                  key={item}
                  label={item}
                  checked={propertyTypes.includes(item)}
                  count={facetsQuery.data?.property_type?.find((bucket) => bucket.value === item)?.count}
                  onChange={() => {
                    setPropertyTypes((current) => toggle(current, item))
                    resetPaging()
                  }}
                />
              ))}
            </FilterGroup>

            <FilterGroup title='BHK'>
              {BHK_OPTIONS.map((item) => (
                <CheckLine
                  key={item}
                  label={item === 4 ? '4+' : `${item}`}
                  checked={bhk.includes(item)}
                  count={facetsQuery.data?.bhk?.find((bucket) => Number(bucket.value) === item)?.count}
                  onChange={() => {
                    setBhk((current) => toggle(current, item))
                    resetPaging()
                  }}
                />
              ))}
            </FilterGroup>

            <FilterGroup title='Furnishing'>
              {FURNISHING.map((item) => (
                <CheckLine
                  key={item}
                  label={item}
                  checked={furnishing.includes(item)}
                  count={facetsQuery.data?.furnishing?.find((bucket) => bucket.value === item)?.count}
                  onChange={() => {
                    setFurnishing((current) => toggle(current, item))
                    resetPaging()
                  }}
                />
              ))}
            </FilterGroup>
          </div>
        </aside>

        <div className='flex min-h-0 flex-col border border-zinc-800 bg-zinc-950'>
          <div className='flex items-center justify-between gap-3 border-b border-zinc-800 p-3'>
            <div className='text-sm text-zinc-400'>
              {selected.length > 0 ? `${selected.length} selected` : 'No rows selected'}
            </div>
            <div className='flex items-center gap-2'>
              <Button
                variant='destructive'
                size='sm'
                onClick={deleteSelected}
                disabled={selected.length === 0 || deleteMutation.isPending}
              >
                <Trash2 className='mr-2 h-4 w-4' />
                Delete
              </Button>
              <Button variant='outline' size='icon' disabled={offset === 0} onClick={() => setOffset(Math.max(0, offset - LIMIT))}>
                <ChevronLeft className='h-4 w-4' />
              </Button>
              <Button
                variant='outline'
                size='icon'
                disabled={offset + LIMIT >= total}
                onClick={() => setOffset(offset + LIMIT)}
              >
                <ChevronRight className='h-4 w-4' />
              </Button>
            </div>
          </div>

          <div className='min-h-0 flex-1 overflow-auto'>
            <table className='w-full border-collapse text-left text-sm'>
              <thead className='sticky top-0 z-10 bg-zinc-900 text-xs uppercase text-zinc-500'>
                <tr>
                  <th className='w-10 border-b border-zinc-800 px-3 py-3'>
                    <input
                      type='checkbox'
                      checked={allVisibleSelected}
                      onChange={() => {
                        setSelected((current) =>
                          allVisibleSelected
                            ? current.filter((id) => !listings.some((listing) => listing.id === id))
                            : Array.from(new Set([...current, ...listings.map((listing) => listing.id)])),
                        )
                      }}
                    />
                  </th>
                  <th className='border-b border-zinc-800 px-3 py-3'>ID</th>
                  <th className='border-b border-zinc-800 px-3 py-3'>Transaction</th>
                  <th className='border-b border-zinc-800 px-3 py-3'>Property</th>
                  <th className='border-b border-zinc-800 px-3 py-3'>Location</th>
                  <th className='border-b border-zinc-800 px-3 py-3'>BHK</th>
                  <th className='border-b border-zinc-800 px-3 py-3'>Sqft</th>
                  <th className='border-b border-zinc-800 px-3 py-3'>Price</th>
                  <th className='border-b border-zinc-800 px-3 py-3'>Confidence</th>
                </tr>
              </thead>
              <tbody className='divide-y divide-zinc-800'>
                {listingsQuery.isLoading ? (
                  <tr>
                    <td colSpan={9} className='px-3 py-10 text-center text-zinc-500'>
                      Loading listings...
                    </td>
                  </tr>
                ) : listings.length === 0 ? (
                  <tr>
                    <td colSpan={9} className='px-3 py-10 text-center text-zinc-500'>
                      No listings match these filters.
                    </td>
                  </tr>
                ) : (
                  listings.map((listing) => (
                    <tr key={listing.id} className='hover:bg-zinc-900/70'>
                      <td className='px-3 py-3'>
                        <input
                          type='checkbox'
                          checked={selected.includes(listing.id)}
                          onChange={() => setSelected((current) => toggle(current, listing.id))}
                        />
                      </td>
                      <td className='font-mono-data max-w-[150px] truncate px-3 py-3 text-xs text-cyan-200'>
                        <button
                          className='hover:underline'
                          onClick={() => {
                            setActiveListingId(listing.id)
                            setOpenSource(true)
                          }}
                        >
                          {listing.id}
                        </button>
                      </td>
                      <td className='px-3 py-3'>{listing.transaction_type}</td>
                      <td className='px-3 py-3'>{listing.property_type}</td>
                      <td className='px-3 py-3'>{listing.location ?? '-'}</td>
                      <td className='px-3 py-3'>{listing.bhk ?? '-'}</td>
                      <td className='px-3 py-3'>{listing.sqft ?? '-'}</td>
                      <td className='font-mono-data px-3 py-3'>{formatPrice(listing)}</td>
                      <td className='px-3 py-3'>{Math.round(listing.confidence_score * 100)}%</td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </div>
      </div>

      <SourceViewerModal
        open={openSource}
        onOpenChange={setOpenSource}
        source={sourceQuery.data}
        loading={sourceQuery.isLoading}
        error={sourceQuery.isError ? 'Could not load the raw WhatsApp source for this listing.' : undefined}
      />
    </section>
  )
}

const FilterGroup = ({ title, children }: { title: string; children: ReactNode }) => (
  <fieldset className='space-y-2'>
    <legend className='text-xs font-medium uppercase text-zinc-500'>{title}</legend>
    <div className='space-y-1'>{children}</div>
  </fieldset>
)

const CheckLine = ({
  label,
  checked,
  count,
  onChange,
}: {
  label: string
  checked: boolean
  count?: number
  onChange: () => void
}) => (
  <label className='flex cursor-pointer items-center justify-between gap-3 rounded-md px-2 py-1.5 text-sm text-zinc-300 hover:bg-zinc-900'>
    <span className='flex items-center gap-2'>
      <input type='checkbox' checked={checked} onChange={onChange} />
      {label}
    </span>
    {count !== undefined ? <span className='font-mono-data text-xs text-zinc-500'>{count}</span> : null}
  </label>
)
