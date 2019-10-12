# selection_manager.py
#
# Copyright 2019 Romain F. T.
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

from gi.repository import Gtk, Gdk, Gio, GdkPixbuf, GLib, Pango
import cairo

class DrawingSelectionManager():
	__gtype_name__ = 'DrawingSelectionManager'

	def __init__(self, image):
		self.image = image
		self.init_pixbuf()

		builder = Gtk.Builder.new_from_resource( \
		                        '/com/github/maoschanz/drawing/ui/selection.ui')
		menu_r = builder.get_object('inactive-selection-menu')
		self.menu_if_inactive = Gtk.Popover.new_from_model(self.image, menu_r)
		menu_l = builder.get_object('active-selection-menu')
		self.menu_if_active = Gtk.Popover.new_from_model(self.image, menu_l)
		self.set_popovers_position(1.0, 1.0)

	def init_pixbuf(self):
		# print('⇒ init pixbuf')
		self.selection_pixbuf = GdkPixbuf.Pixbuf.new(GdkPixbuf.Colorspace.RGB, \
		                                                          True, 8, 1, 1)

		self.set_coords(True, 0, 0)
		self.selection_path = None
		self.temp_path = None

		self.is_active = False
		self.has_been_used = False
		self.is_imported_data = False # this default value means nothing

	def load_from_path(self, new_path):
		"""Create a selection_pixbuf from a minimal part of the main surface by
		erasing everything outside of the provided path."""
		if new_path is None:
			return # TODO throw something goddammit
		else:
			self.selection_path = new_path
			print(self, "affectation d'un path de sélection", self.image)
		main_pixbuf = self.image.get_main_pixbuf()

		# Erase everything outside of the path
		surface = Gdk.cairo_surface_create_from_pixbuf(main_pixbuf, 0, None)
		cairo_context = cairo.Context(surface)
		cairo_context.set_operator(cairo.Operator.DEST_IN)
		cairo_context.new_path()
		cairo_context.append_path(self.selection_path)
		if self.temp_path is None: # XXX condition utile?? on dirait bien
			self._set_temp_path(cairo_context.copy_path())
		# else:
		# 	print('selection manager ligne 63')
		cairo_context.fill_preserve()
		cairo_context.set_operator(cairo.Operator.OVER)

		# Find the coords to reduce the size of what will be stored
		main_width = main_pixbuf.get_width()
		main_height = main_pixbuf.get_height()
		xmin, ymin, xmax, ymax = cairo_context.path_extents()
		xmax = min(xmax, main_width)
		ymax = min(ymax, main_height)
		xmin = int( max(xmin, 0.0) ) # If everything is right, this is selection_x
		ymin = int( max(ymin, 0.0) ) # If everything is right, this is selection_y
		if self.selection_x < 0:
			xmin = self.selection_x
		if self.selection_y < 0:
			ymin = self.selection_y

		# Actually store the pixbuf
		selection_width = int(xmax - xmin)
		selection_height = int(ymax - ymin)
		if selection_width > 0 and selection_height > 0:
			# print('⇒ load pixbuf')
			self.selection_pixbuf = Gdk.pixbuf_get_from_surface(surface, \
			            int(xmin), int(ymin), selection_width, selection_height)
			# XXX PAS_SOUHAITABLE ?? passer par set_pixbuf est-il plus sain ?
			# avec un try except déjà ce serait pas mal
		else:
			self.reset()
		self.image.update_actions_state()

	def set_coords(self, temp_too, x, y):
		self.selection_x = x
		self.selection_y = y
		if temp_too:
			self.temp_x = x
			self.temp_y = y

	def set_pixbuf(self, pixbuf, use_import_param, is_imported_data):
		if use_import_param:
			self.is_imported_data = is_imported_data
		self.temp_path = None
		# print('⇒ set pixbuf')
		self.selection_pixbuf = pixbuf
		self._create_path_from_pixbuf(not self.is_imported_data)

	def get_pixbuf(self):
		return self.selection_pixbuf

	def reset(self):
		# print('⇒ reset pixbuf')
		self.selection_pixbuf = None
		self.selection_path = None
		self.set_coords(True, 0, 0)
		self.temp_path = None
		self.is_active = False
		# self.image.use_stable_pixbuf() # XXX empêchait la suppression de la
		       # sélection, mais peut-être que ça avait du sens que ce soit là ?
		self.image.update_actions_state()
		self.image.update()

	def delete_temp(self):
		if self.temp_path is None:
			return
		if not self.is_active:
			return
		cairo_context = self._get_context()
		cairo_context.new_path()
		cairo_context.append_path(self.temp_path)
		cairo_context.clip()
		cairo_context.set_operator(cairo.Operator.CLEAR)
		cairo_context.paint()
		cairo_context.set_operator(cairo.Operator.OVER)

	def get_path_with_scroll(self):
		if self.selection_path is None:
			return None # TODO throw something goddammit
		cairo_context = self._get_context()
		delta_x = 0 - self.image.scroll_x + self.selection_x - self.temp_x
		delta_y = 0 - self.image.scroll_y + self.selection_y - self.temp_y
		for pts in self.selection_path:
			if pts[1] is not ():
				x = pts[1][0] + delta_x
				y = pts[1][1] + delta_y
				cairo_context.line_to(int(x), int(y))
		cairo_context.close_path()
		return cairo_context.copy_path()

	def correct_coords(self, x1, x2, y1, y2, with_selection_coords):
		x1 -= self.image.scroll_x
		x2 -= self.image.scroll_x
		y1 -= self.image.scroll_y
		y2 -= self.image.scroll_y
		if with_selection_coords:
			x1 += self.selection_x
			x2 += self.selection_x
			y1 += self.selection_y
			y2 += self.selection_y
		return x1, x2, y1, y2

	def show_selection_on_surface(self, cairo_context, with_scroll):
		if self.selection_pixbuf is None:
			return # TODO throw something goddammit
		if with_scroll:
			x = self.selection_x - self.image.scroll_x
			y = self.selection_y - self.image.scroll_y
		else:
			x = self.selection_x
			y = self.selection_y
		Gdk.cairo_set_source_pixbuf(cairo_context, self.selection_pixbuf, x, y)
		cairo_context.paint()

	############################################################################

	def _create_path_from_pixbuf(self, delete_path_content):
		"""This method creates a rectangle selection from the currently set
		selection pixbuf.
		It can be the result of an editing operation (crop, scale, etc.), or it
		can be an imported picture (from a file or from the clipboard).
		In the first case, the "delete_path_content" boolean parameter should be
		true, so the temp_path will be cleared."""
		if self.selection_pixbuf is None:
			return # TODO throw something goddammit
		self.has_been_used = True
		self.is_active = True
		cairo_context = self._get_context()
		cairo_context.move_to(self.selection_x, self.selection_y)
		cairo_context.rel_line_to(self.selection_pixbuf.get_width(), 0)
		cairo_context.rel_line_to(0, self.selection_pixbuf.get_height())
		cairo_context.rel_line_to(-1 * self.selection_pixbuf.get_width(), 0)
		cairo_context.close_path()
		self.selection_path = cairo_context.copy_path()
		if delete_path_content:
			self._set_temp_path(cairo_context.copy_path())
		else:
			self.temp_x = self.selection_x
			self.temp_y = self.selection_y
		self.hide_popovers()
		self.image.update_actions_state()

	def _set_temp_path(self, new_path):
		print(self, "affectation d'un path temporaire :\n", new_path)
		self.temp_x = self.selection_x
		self.temp_y = self.selection_y
		self.temp_path = new_path
		self.is_active = True

	def point_is_in_selection(self, tested_x, tested_y):
		"""Returns a boolean if the point whose coordinates are "(tested_x,
		tested_y)" is in the path defining the selection. If such path doesn't
		exist, it returns None."""
		if not self.is_active:
			return True # TODO throw something goddammit
		if self.selection_path is None:
			return None # TODO throw something goddammit
		cairo_context = self._get_context()
		for pts in self.selection_path:
			if pts[1] is not ():
				x = pts[1][0] + self.selection_x - self.temp_x
				y = pts[1][1] + self.selection_y - self.temp_y
				cairo_context.line_to(int(x), int(y))
		return cairo_context.in_fill(tested_x, tested_y)

	def _get_context(self):
		return cairo.Context(self.image.surface)

	############################################################################
	# Popover menus management methods #########################################

	def set_popovers_position(self, x, y):
		rectangle = Gdk.Rectangle()
		rectangle.x = int(x)
		rectangle.y = int(y)
		rectangle.height = 1
		rectangle.width = 1
		self.menu_if_inactive.set_pointing_to(rectangle)
		self.menu_if_active.set_pointing_to(rectangle)

	def hide_popovers(self):
		self.menu_if_active.popdown()
		self.menu_if_inactive.popdown()

	def show_popover(self):
		if self.is_active:
			self.menu_if_active.popup()
		else:
			gdk_rect = self.menu_if_inactive.get_pointing_to()[1]
			# It's important to pre-set these coords as the selection coords,
			# because right-click → import/paste shouldn't use (0, 0) as coords.
			self.set_coords(True, gdk_rect.x, gdk_rect.y)
			self.menu_if_inactive.popup()

	############################################################################
	# Debug ####################################################################

	def print_values(self, *args):
		"""Debug only. Is linked to the "troubleshoot selection" item in the
		short hamburger menu."""
		print("selection_x", self.selection_x)
		print("selection_y", self.selection_y)
		print("temp_x", self.temp_x)
		print("temp_y", self.temp_y)
		print("image.scroll_x", self.image.scroll_x)
		print("image.scroll_y", self.image.scroll_y)
		print("image.zoom_level", self.image.zoom_level)

		print("selection_path with scroll & temp deltas")
		delta_x = 0 - self.image.scroll_x + self.selection_x - self.temp_x
		delta_y = 0 - self.image.scroll_y + self.selection_y - self.temp_y
		for pts in self.selection_path:
			if pts[1] is not ():
				x = pts[1][0] + delta_x
				y = pts[1][1] + delta_y
				print('\t', x, y)

		print("has_been_used", self.has_been_used) # TODO not implemented
		print("---------------------------------------------------------------")

	############################################################################
################################################################################

