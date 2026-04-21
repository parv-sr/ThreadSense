const requiredVars = {
  VITE_SUPABASE_URL: import.meta.env.VITE_SUPABASE_URL,
  VITE_SUPABASE_ANON_KEY: import.meta.env.VITE_SUPABASE_ANON_KEY,
} as const

Object.entries(requiredVars).forEach(([key, value]) => {
  if (!value) {
    console.error(`[ThreadSense] Missing required environment variable: ${key}`)
  }
})

export const env = {
  supabaseUrl: requiredVars.VITE_SUPABASE_URL || '',
  supabaseAnonKey: requiredVars.VITE_SUPABASE_ANON_KEY || '',
  apiUrl: import.meta.env.VITE_API_URL ?? '',
}
