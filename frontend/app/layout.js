import "./globals.css";

export const metadata = {
  title: "AI Face Tracker",
  description: "Live facial landmarks, blink detection, and head movement tracking.",
};

export default function RootLayout({ children }) {
  return <html lang="en"><body>{children}</body></html>;
}
