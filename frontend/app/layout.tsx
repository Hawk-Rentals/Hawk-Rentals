import type { ReactNode } from "react";
import Link from "next/link";
import "./globals.css";

export const metadata = {
  title: "Hawk Rentals | Your next move starts here",
  description: "Browse the Hawk Rentals fleet, check availability, and reserve your next drive.",
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en">
      <body>
        <header className="site-header">
          <Link className="brand" href="/" aria-label="Hawk Rentals home"><span className="brand-mark">H</span> HAWK<span className="brand-sub">RENTALS</span></Link>
          <nav aria-label="Main navigation"><Link href="/vehicles">Our fleet</Link><Link href="/#reserve">Book a vehicle <span aria-hidden="true">↗</span></Link><Link className="staff-link" href="/staff">Staff portal</Link></nav>
        </header>
        {children}
        <footer><Link className="brand" href="/">HAWK RENTALS</Link><span>A good drive starts here.</span><span>© {new Date().getFullYear()} Hawk Rentals</span></footer>
      </body>
    </html>
  );
}
