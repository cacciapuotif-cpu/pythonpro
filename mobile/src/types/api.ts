import { z } from 'zod';

/**
 * API Types and Zod Schemas
 */

// ============== Auth ==============
export const LoginRequestSchema = z.object({
  email: z.string().email('Email non valida'),
  password: z.string().min(6, 'Password deve essere almeno 6 caratteri'),
});

export const TokenResponseSchema = z.object({
  access_token: z.string(),
  refresh_token: z.string().optional(),
  token_type: z.string().default('bearer'),
  expires_in: z.number().optional(),
});

export const UserSchema = z.object({
  id: z.number(),
  email: z.string().email(),
  nome: z.string(),
  cognome: z.string().optional(),
  ruolo: z.string().optional(),
});

export type LoginRequest = z.infer<typeof LoginRequestSchema>;
export type TokenResponse = z.infer<typeof TokenResponseSchema>;
export type User = z.infer<typeof UserSchema>;

// ============== Items (Generic Resource) ==============
export const ItemSchema = z.object({
  id: z.number(),
  nome: z.string(),
  descrizione: z.string().optional().nullable(),
  stato: z.string().optional(),
  data_creazione: z.string().optional(),
  data_modifica: z.string().optional(),
});

export const ItemsListResponseSchema = z.object({
  items: z.array(ItemSchema),
  total: z.number().optional(),
  page: z.number().optional(),
  page_size: z.number().optional(),
});

export type Item = z.infer<typeof ItemSchema>;
export type ItemsListResponse = z.infer<typeof ItemsListResponseSchema>;

// ============== API Error ==============
export const ApiErrorSchema = z.object({
  detail: z.union([
    z.string(),
    z.array(z.object({
      loc: z.array(z.union([z.string(), z.number()])),
      msg: z.string(),
      type: z.string(),
    })),
  ]),
  status_code: z.number().optional(),
});

export type ApiError = z.infer<typeof ApiErrorSchema>;

// ============== Generic API Response ==============
export interface ApiResponse<T> {
  data: T;
  error?: string;
}

export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
}

// ============== Gestionale ==============

// Collaboratori
export const CollaboratoreSchema = z.object({
  id: z.number(),
  first_name: z.string(), // Backend restituisce first_name
  last_name: z.string(), // Backend restituisce last_name
  email: z.string().email().optional().nullable(),
  phone: z.string().optional().nullable(), // Backend restituisce phone
  fiscal_code: z.string().optional().nullable(), // Backend restituisce fiscal_code
  position: z.string().optional().nullable(), // Backend restituisce position
  documento_identita_filename: z.string().optional().nullable(),
  curriculum_filename: z.string().optional().nullable(),
  created_at: z.string().optional(), // Backend restituisce created_at
  updated_at: z.string().optional().nullable(),
}).transform(data => ({
  // Trasforma i nomi inglesi in italiani per l'app
  id: data.id,
  nome: data.first_name,
  cognome: data.last_name,
  email: data.email,
  telefono: data.phone,
  codice_fiscale: data.fiscal_code,
  ruolo: data.position,
  path_documento_identita: data.documento_identita_filename,
  path_curriculum: data.curriculum_filename,
  data_creazione: data.created_at,
  data_modifica: data.updated_at,
}));

export type Collaboratore = z.infer<typeof CollaboratoreSchema>;

// Enti Attuatori
export const EnteSchema = z.object({
  id: z.number(),
  ragione_sociale: z.string(),
  partita_iva: z.string(),
  codice_fiscale: z.string().optional().nullable(),
  sede_legale: z.string().optional().nullable(),
  citta: z.string().optional().nullable(),
  cap: z.string().optional().nullable(),
  provincia: z.string().optional().nullable(),
  email: z.string().email().optional().nullable(),
  pec: z.string().email().optional().nullable(),
  telefono: z.string().optional().nullable(),
  iban: z.string().optional().nullable(),
  path_logo: z.string().optional().nullable(),
  is_active: z.boolean().default(true),
  data_creazione: z.string().optional(),
  data_modifica: z.string().optional(),
});

export type Ente = z.infer<typeof EnteSchema>;

// Progetti
export const ProgettoSchema = z.object({
  id: z.number(),
  name: z.string(), // Backend restituisce name
  description: z.string().optional().nullable(), // Backend restituisce description
  status: z.string().optional().nullable(), // Backend restituisce status
  start_date: z.string().optional().nullable(), // Backend restituisce start_date
  end_date: z.string().optional().nullable(), // Backend restituisce end_date
  cup: z.string().optional().nullable(),
  ente_erogatore: z.string().optional().nullable(),
  created_at: z.string().optional(), // Backend restituisce created_at
  updated_at: z.string().optional().nullable(),
}).transform(data => ({
  // Trasforma i nomi inglesi in italiani per l'app
  id: data.id,
  titolo: data.name,
  descrizione: data.description,
  codice_progetto: data.cup,
  stato: data.status,
  data_inizio: data.start_date,
  data_fine: data.end_date,
  budget: null,
  ore_previste: null,
  ore_effettive: null,
  implementing_entity_id: null,
  data_creazione: data.created_at,
  data_modifica: data.updated_at,
}));

export type Progetto = z.infer<typeof ProgettoSchema>;

// Calendario (Presenze)
export const EventoSchema = z.object({
  id: z.number(),
  collaborator_id: z.number(),
  project_id: z.number(),
  assignment_id: z.number().optional().nullable(),
  date: z.string(), // Backend restituisce date
  start_time: z.string(), // Backend restituisce start_time
  end_time: z.string(), // Backend restituisce end_time
  hours: z.number().optional().nullable(), // Backend restituisce hours
  notes: z.string().optional().nullable(),
  created_at: z.string().optional(), // Backend restituisce created_at
  updated_at: z.string().optional().nullable(),
}).transform(data => ({
  // Trasforma i nomi inglesi in italiani per l'app
  id: data.id,
  collaborator_id: data.collaborator_id,
  project_id: data.project_id,
  data: data.date,
  ora_inizio: data.start_time,
  ora_fine: data.end_time,
  ore_lavorate: data.hours,
  note: data.notes,
  luogo: null,
  tipo_attivita: null,
  stato: null,
  data_creazione: data.created_at,
  data_modifica: data.updated_at,
}));

export type Evento = z.infer<typeof EventoSchema>;
