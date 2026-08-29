/**
 * The entry sequence is built from six real photographs of a KSP station,
 * shown in order as the visitor scrolls in, signs in, and walks through the
 * front door. `keyframe` is the position (0..1) each photo occupies along
 * the master scene-progress timeline — see StationBackdrop.jsx.
 */
export const STATION_SCENES = [
  { id: 1, keyframe: 0.0, src: '/images/station/scene-1.jpg', alt: 'Aerial view of the station compound', objectPosition: '50% 50%' },
  { id: 2, keyframe: 0.2, src: '/images/station/scene-2.jpg', alt: 'Station facade, eye level', objectPosition: '50% 45%' },
  { id: 3, keyframe: 0.4, src: '/images/station/scene-3.jpg', alt: 'Station signage above the entrance', objectPosition: '50% 40%' },
  { id: 4, keyframe: 0.6, src: '/images/station/scene-4.jpg', alt: 'Closed main entrance door', objectPosition: '50% 45%' },
  { id: 5, keyframe: 0.8, src: '/images/station/scene-5.jpg', alt: 'Main door opening onto the lobby', objectPosition: '50% 45%' },
  { id: 6, keyframe: 1.0, src: '/images/station/scene-6.jpg', alt: 'Interior hall with case room doors', objectPosition: '50% 50%' },
]

/** Scroll covers scenes 1-4 (keyframes 0 -> 0.6). The gate sits at scene 4. */
export const GATE_PROGRESS = 0.6
/** Post-login cutscene animates from the closed door to the hall (0.6 -> 1.0). */
export const HUB_PROGRESS = 1.0

/**
 * The six rooms of the main hall, reached once the door opens. Dashboard is
 * the hall itself (the central, default destination); the rest map onto the
 * six feature routes already served by the working application — see
 * src/App.jsx and src/components/Sidebar.jsx. `labelKey`/`badgeKey` reuse
 * the app's own translation keys so the hub follows the language toggle
 * exactly like the rest of KAVACH.
 */
export const HUB_OPTIONS = [
  {
    id: 'dashboard',
    route: '/',
    labelKey: 'navDashboard',
    eyebrow: 'Main Hall',
    description: 'District crime overview & case load at a glance',
    icon: 'LayoutDashboard',
    central: true,
  },
  {
    id: 'chat',
    route: '/chat',
    labelKey: 'navChat',
    eyebrow: 'A.I. Communication Room',
    description: 'Ask the investigator AI about any case',
    icon: 'MessageSquare',
  },
  {
    id: 'network',
    route: '/network',
    labelKey: 'navNetwork',
    eyebrow: 'Interrogation Room',
    description: 'Suspect & evidence relationship graph',
    icon: 'Network',
  },
  {
    id: 'analytics',
    route: '/analytics',
    labelKey: 'navAnalytics',
    eyebrow: 'Analytics Bureau',
    description: 'Crime trends, hotspots & demographic insight',
    icon: 'BarChart2',
  },
  {
    id: 'cases',
    route: '/cases',
    labelKey: 'navCases',
    eyebrow: 'Records Room',
    description: 'Chronological FIR records & case management',
    icon: 'FolderOpen',
  },
  {
    id: 'profiles',
    route: '/profiles',
    labelKey: 'navProfiles',
    eyebrow: 'Identification Wing',
    description: 'Accused profiles, history & known associates',
    icon: 'Users',
  },
]
