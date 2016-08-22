import os
import datetime
import pandas

import sqlite3

import networkx

from util import wgs84_distance

from gtfs import GTFS
import unittest


class TestGTFS(unittest.TestCase):

    """
    Test data can be found under test_data/ directory.
    """

    @classmethod
    def setUpClass(cls):
        """ This method is run once before executing any tests"""
        cls.gtfs_source_dir = os.path.join(os.path.dirname(__file__), "test_data")
        cls.G = GTFS.from_directory_as_inmemory_db(cls.gtfs_source_dir)

    def setUp(self):
        """This method is run once before _each_ test method is executed"""
        self.gtfs_source_dir = self.__class__.gtfs_source_dir
        self.G = self.__class__.G
        # GTFS.from_directory_as_inmemory_db(self.gtfs_source_dir)
        # os.path.join(os.path.dirname(__file__), "test_data")

    def tearDown(self):
        """This method is run once after _each_ test method is executed"""
        pass

    def test_get_cursor(self):
        assert isinstance(self.G.get_cursor(), sqlite3.Cursor)

    def test_tzset(self):
        """ How to test this properly?"""
        pass

    def test_get_timezone_name(self):
        assert isinstance(self.G.get_timezone_string(), str)

    def test_get_day_start_ut(self):
        """ America/Los_Angeles on 2016,1,1 should map to -07:00 when DST IS in place"""
        date = datetime.datetime(2016, 6, 15)
        epoch = datetime.datetime(1970, 1, 1)
        day_start_utc_ut = (date - epoch).total_seconds()
        # day starts 7 hours later in Los Angeles
        day_start_ut_test = day_start_utc_ut + 7 * 3600
        day_start_ut_code = self.G.get_day_start_ut(date)
        # print day_start_ut_test - day_start_ut_code
        assert day_start_ut_test == day_start_ut_code

    def test_get_main_database_path(self):
        assert self.G.get_main_database_path() == "", "in memory database should equal ''"

        from import_gtfs import import_gtfs
        try:
            fname = self.gtfs_source_dir + "/test_gtfs.sqlite"
            if os.path.exists(fname) and os.path.isfile(fname):
                os.remove(fname)
            conn = sqlite3.connect(fname)
            import_gtfs(self.gtfs_source_dir, conn, preserve_connection=True, print_progress=False)
            G = GTFS(conn)
            assert os.path.exists(G.get_main_database_path())
            assert "/test_gtfs.sqlite" in G.get_main_database_path(), "path should be correct"
        finally:
            if os.path.exists(fname) and os.path.isfile(fname):
                os.remove(fname)

    def test_get_table(self):
        df = self.G.get_table("agencies")
        assert isinstance(df, pandas.DataFrame)

    def test_get_table_names(self):
        tables = self.G.get_table_names()
        assert isinstance(tables, list)
        assert len(tables) > 11, "quite many tables should be available"
        assert "routes" in tables

    def test_to_directed_graph(self):
        # test that distance works
        all_link_attributes = ["duration_min", "duration_max", "duration_median",
                               "duration_avg", "n_vehicles", "route_types",
                               "distance_straight_line", "distance_shape",
                               "route_ids"]
        nxGraph = self.G.to_directed_graph(link_attributes=all_link_attributes)
        assert isinstance(nxGraph, networkx.DiGraph), type(nxGraph)
        nodes = nxGraph.nodes(data=True)
        assert len(nodes) > 0
        for node in nodes:
            node_attrs = node[1]
            node_id = node[0]
            assert isinstance(node_id, int)
            assert "lat" in node_attrs
            assert "lon" in node_attrs
            assert "name" in node_attrs
        edges = nxGraph.edges(data=True)
        assert len(edges) > 0
        from_I, to_I, linkData = edges[0]
        for link_attr in all_link_attributes:
            assert link_attr in linkData, "no " + link_attr + " found"
            if "duration_" in link_attr:
                assert linkData[link_attr] >= 0

        at_least_one_shape_distance = False
        for from_I, to_I, linkData in edges:
            ds = linkData['distance_shape']
            assert isinstance(ds, int) or (ds is None)
            if isinstance(ds, int):
                at_least_one_shape_distance = True
            assert linkData['duration_min'] <= linkData["duration_avg"]
            assert linkData['duration_avg'] <= linkData["duration_max"]
            assert linkData['duration_median'] <= linkData["duration_max"]
            assert linkData['duration_median'] >= linkData["duration_min"]
            assert isinstance(linkData['distance_straight_line'], float)
            n_veh = linkData["n_vehicles"]
            route_types = linkData["route_types"]
            route_types_sum = sum([count for route_type, count in route_types.iteritems()])
            assert n_veh == route_types_sum
            route_ids = linkData["route_ids"]
            route_ids_sum = sum([count for route_type, count in route_ids.iteritems()])
            assert n_veh == route_ids_sum

        # print self.G.get_table("trips")
        # print "printing tables:\n\n"
        # print self.G.get_table("stop_times")
        # print self.G.get_table("shapes")
        # # print self.G.get_table("stops")
        assert at_least_one_shape_distance, "no shape distances were found"

    def test_to_undirected_line_graph(self):
        G = self.G.to_undirected_line_graph()
        assert len(G.nodes()) > 0
        assert len(G.edges()) > 0
        for from_node, to_node, data in G.edges(data=True):
            assert "route_ids" in data
            assert isinstance(from_node, int)
            assert isinstance(to_node, int)
            assert from_node in G.nodes()
            assert to_node in G.nodes()
        for node, data in G.nodes(data=True):
            assert "lat" in data
            assert "lon" in data
            assert isinstance(node, int)

    def test_get_all_route_shapes(self):
        res = self.G.get_all_route_shapes()
        assert isinstance(res, list)
        el = res[0]
        keys = "name type agency lats lons".split()
        for key in keys:
            assert key in el
        for el in res:
            assert isinstance(el["name"], (str, unicode))
            assert isinstance(el["type"], int)
            assert isinstance(el["agency"], (str, unicode))
            assert isinstance(el["lats"], list), type(el['lats'])
            assert isinstance(el["lons"], list)
            assert isinstance(el['lats'][0], float)
            assert isinstance(el['lons'][0], float)

    def test_to_aggregate_line_graph(self):
        net_old = self.G.to_undirected_line_graph()
        net = self.G.to_aggregate_line_graph(1000)
        assert len(net_old.nodes()) > len(net.nodes())
        assert isinstance(net, networkx.Graph)
        net = self.G.to_aggregate_line_graph(0)
        print len(net_old.nodes())
        assert len(net_old.nodes()) == len(net.nodes())

    def test_get_shape_distance_between_stops(self):
        # tested as a part of test_to_directed_graph, although this could be made a separate test as well
        pass

    def test_copy_and_filter(self):
        from import_gtfs import import_gtfs
        import hashlib
        try:
            # some preparations:
            fname = self.gtfs_source_dir + "/test_gtfs.sqlite"
            fname_copy = self.gtfs_source_dir + "/test_gtfs_copy.sqlite"
            for fn in [fname, fname_copy]:
                if os.path.exists(fn) and os.path.isfile(fn):
                    os.remove(fn)
            assert not os.path.exists(fname_copy)
            conn = sqlite3.connect(fname)

            import_gtfs(self.gtfs_source_dir, conn, preserve_connection=True, print_progress=False)

            # do a simple copy
            G = GTFS(conn)
            G.copy_and_filter(fname_copy, update_metadata=False)
            # check that the copying has been properly performed:
            hash_orig = hashlib.md5(open(fname, 'rb').read()).hexdigest()
            hash_copy = hashlib.md5(open(fname_copy, 'rb').read()).hexdigest()
            assert os.path.exists(fname_copy)
            assert hash_orig == hash_copy
            os.remove(fname_copy)

            # A simple test that changing update_metadata to True, does update somestuff:
            G.copy_and_filter(fname_copy, update_metadata=True)
            # check that the copying has been properly performed:
            hash_copy = hashlib.md5(open(fname_copy, 'rb').read()).hexdigest()
            assert os.path.exists(fname_copy)
            assert hash_orig != hash_copy
            os.remove(fname_copy)

            # test filtering by agency:
            G.copy_and_filter(fname_copy, agency_ids_to_preserve=['DTA'])
            hash_copy = hashlib.md5(open(fname_copy, 'rb').read()).hexdigest()
            assert hash_orig != hash_copy
            G_copy = GTFS(fname_copy)
            agency_table = G_copy.get_table("agencies")
            assert "EXA" not in agency_table['agency_id'].values, "EXA agency should not be preserved"
            assert "DTA" in agency_table['agency_id'].values, "DTA agency should be preserved"
            routes_table = G_copy.get_table("routes")
            assert "EXR1" not in routes_table['route_id'].values, "EXR1 route_id should not be preserved"
            assert "AB" in routes_table['route_id'].values, "AB route_id should be preserved"
            trips_table = G_copy.get_table("trips")
            assert "EXT1" not in trips_table['trip_id'].values, "EXR1 route_id should not be preserved"
            assert "AB1" in trips_table['trip_id'].values, "AB1 route_id should be preserved"
            calendar_table = G_copy.get_table("calendar")
            assert "FULLW" in calendar_table['service_id'].values, "FULLW service_id should be preserved"
            # stop_times
            stop_times_table = G_copy.get_table("stop_times")
            # 01:23:45 corresponds to 3600 + (32 * 60) + 45 [in day seconds]
            assert 3600 + (32 * 60) + 45 not in stop_times_table['arr_time']
            os.remove(fname_copy)

            # untested tables with filtering: stops, stops_rtree (non-crucial though), shapes
            # (Shapes are not provided in the test data currently)

            # test filtering by start and end time, copy full range
            G.copy_and_filter(fname_copy, start_date="2007-01-01", end_date="2011-01-01", update_metadata=False)
            hash_copy = hashlib.md5(open(fname_copy, 'rb').read()).hexdigest()
            calendar = G.get_table("calendar")
            # print calendar
            calendar_copy = G_copy.get_table("calendar")
            # print calendar_copy
            assert hash_orig == hash_copy

            G_copy = GTFS(fname_copy)
            dsut_end = G_copy.get_day_start_ut("2010-12-31")
            dsut_to_trip_I = G_copy.get_tripIs_within_range_by_dsut(dsut_end, dsut_end+24*3600)
            assert len(dsut_to_trip_I) > 0
            os.remove(fname_copy)

            # the end date is not included:
            G.copy_and_filter(fname_copy, start_date="2007-01-02", end_date="2010-12-31")
            hash_copy = hashlib.md5(open(fname_copy, 'rb').read()).hexdigest()
            assert hash_orig != hash_copy
            G_copy = GTFS(fname_copy)
            dsut_end = G_copy.get_day_start_ut("2010-12-31")
            dsut_to_trip_I = G_copy.get_tripIs_within_range_by_dsut(dsut_end, dsut_end+24*3600)
            assert len(dsut_to_trip_I) == 0
            calendar_copy = G_copy.get_table("calendar")
            max_date_calendar = max([datetime.datetime.strptime(el, "%Y-%m-%d")
                                     for el in calendar_copy["end_date"].values])
            min_date_calendar = max([datetime.datetime.strptime(el, "%Y-%m-%d")
                                     for el in calendar_copy["start_date"].values])
            end_date_not_included = datetime.datetime.strptime("2010-12-31", "%Y-%m-%d")
            start_date_not_included = datetime.datetime.strptime("2007-01-01", "%Y-%m-%d")
            assert max_date_calendar < end_date_not_included, "the last date should not be included in calendar"
            assert start_date_not_included < min_date_calendar
            os.remove(fname_copy)

            # test that the db is split by a given spatial boundary
            G.copy_and_filter(fname_copy, buffer_lat=36.914893, buffer_lon=-116.76821, buffer_distance=50000)
            G_copy = GTFS(fname_copy)

            stops_table = G_copy.get_table("stops")
            assert "FUR_CREEK_RES" not in stops_table['stop_id'].values
            assert "AMV" in stops_table['stop_id'].values
            assert len(stops_table['stop_id'].values) == 8

            import pandas
            conn_copy = sqlite3.connect(fname_copy)
            stop_ids_df = pandas.read_sql('SELECT stop_id from stop_times '
                                       'left join stops '
                                       'on stops.stop_I = stop_times.stop_I', conn_copy)
            stop_ids = stop_ids_df["stop_id"].values
            # print stop_ids
            assert "FUR_CREEK_RES" not in stop_ids
            assert "AMV" in stop_ids

            trips_table = G_copy.get_table("trips")
            # print trips_table
            assert "BFC1" not in trips_table['trip_id'].values

            routes_table = G_copy.get_table("routes")
            assert "BFC" not in routes_table['route_id'].values
            # cases:
            # whole trip excluded
            # whole route excluded
            # whole agency excluded
            # part of trip excluded
            # part of route excluded
            # part of agency excluded
            # not removing stops from a trip that returns into area
        finally:
            for fn in [fname, fname_copy]:
                if os.path.exists(fn) and os.path.isfile(fn):
                    os.remove(fn)

    def test_get_timezone_string(self):
        tz_string = self.G.get_timezone_string()
        assert len(tz_string) == 5
        assert tz_string[0] in "+-"
        for i in range(1, 5):
            assert tz_string[i] in "0123456789"
        # print tz_name, tz_string
        dt = datetime.datetime(1970, 1, 1)
        tz_string_epoch = self.G.get_timezone_string(dt)
        assert tz_string != tz_string_epoch

    def test_timezone_convertions(self):
        """
        Two methods are tested:
            ut_seconds_to_gtfs_datetime
            unlocalized_datetime_to_ut_seconds
        """
        ut = 10.0
        gtfs_dt = self.G.ut_seconds_to_gtfs_datetime(ut)
        # print gtfs_dt
        unloc_dt = gtfs_dt.replace(tzinfo=None)
        # print unloc_dt
        ut_later = self.G.unlocalized_datetime_to_ut_seconds(unloc_dt)
        # print ut_later
        assert ut == ut_later

    def test_get_trip_trajectory_data_within_timespan(self):
        # untested, really
        s, e = self.G.get_conservative_gtfs_time_span_in_ut()
        res = self.G.get_trip_trajectories_within_timespan(s, s + 3600 * 24)
        assert isinstance(res, dict)

    def test_get_stop_count_data(self):
        start_ut, end_ut = self.G.get_conservative_gtfs_time_span_in_ut()
        df = self.G.get_stop_count_data(start_ut, end_ut)
        assert isinstance(df, pandas.DataFrame)
        columns = ["stop_I", "count", "lat", "lon", "name"]
        for c in columns:
            assert c in df.columns
            el = df[c].iloc[0]
            if c in ["stop_I", "count"]:
                assert isinstance(el,  int)
            if c in ["lat", "lon"]:
                assert isinstance(el, float)
            if c in ["name"]:
                assert isinstance(el, (str, unicode)), type(el)
        assert (df['count'].values > 0).any()

    def test_get_segment_count_data(self):
        s, e = self.G.get_conservative_gtfs_time_span_in_ut()
        res = self.G.get_segment_count_data(s, e, use_shapes=True)
        assert len(res) > 0
        assert res is not None, "this is a it compiles test"

    def test_get_tripIs_active_in_range(self):
        # one line in calendar.txt:
        #  FULLW,1,1,1,1,1,1,1,20070101,20101231
        # one line in trips.txt
        #  AB,FULLW,AB1,to Bullfrog,0,1,
        # lines in stop_times.txt
        #  AB1, 8:00:00, 8:00:00, BEATTY_AIRPORT,1,,,,
        #  AB1, 8:10:00, 8:15:00, BULLFROG, 2,,,,
        dt_start_query = datetime.datetime(2007, 1, 1, 7, 59, 59)
        dt_end_query = datetime.datetime(2007, 1, 1, 8, 2, 01)
        dt_start_real = datetime.datetime(2007, 1, 1, 8, 0, 00)
        dt_end_real = datetime.datetime(2007, 1, 1, 8, 10, 00)
        start_query = self.G.unlocalized_datetime_to_ut_seconds(dt_start_query)
        end_query = self.G.unlocalized_datetime_to_ut_seconds(dt_end_query)
        start_real = self.G.unlocalized_datetime_to_ut_seconds(dt_start_real)
        end_real = self.G.unlocalized_datetime_to_ut_seconds(dt_end_real)

        found = False
        df = self.G.get_tripIs_active_in_range(start_query, end_query)
        for row in df.itertuples():
            assert (row.start_time_ut <= end_query) and \
                   (row.end_time_ut >= start_query), "some trip does not overlap!"
            if row.start_time_ut == start_real and row.end_time_ut == end_real:
                found = True
                # check that overlaps
        # for debugging::
        # if not found:
        #     print start_real, end_real
        #     for h in header:
        #         print h + " |",
        #     print ""
        #     for row in rows:
        #         for el in row:
        #             print el,
        #         print ""
        assert found, "a trip that should be found is not found"

    def test_get_trip_counts_per_day(self):
        df = self.G.get_trip_counts_per_day()
        columns = "dates trip_counts".split(" ")
        for c in columns:
            assert c in df.columns
        el = df.iloc[0]
        assert isinstance(el["dates"], (str, unicode))
        assert isinstance(el["trip_counts"], int)

    def test_get_spreading_trips(self):
        pass  # untested

    def test_get_closest_stop(self):
        # First row in test_data:
        # FUR_CREEK_RES, Furnace Creek Resort (Demo),, 36.425288, -117.133162,,
        lat_s, lon_s = 36.425288, -117.133162
        lat, lon = lat_s + 10**-5, lon_s + 10**-5
        stop_I = self.G.get_closest_stop(lat, lon)
        assert isinstance(stop_I, int)
        df = self.G.get_stop_info(stop_I)
        name = df['name'][0]
        # print name
        # check that correct stop has been found:
        assert name == "Furnace Creek Resort (Demo)"
        # distance to the stop should be below 50 meters for such a small separation:
        assert wgs84_distance(lat, lon, lat_s, lon_s) < 50

    def test_get_route_name_and_type_of_tripI(self):
        # just a simple random test:
        trip_I = 1
        name, type_ = self.G.get_route_name_and_type_of_tripI(trip_I)
        assert isinstance(name, unicode)
        assert isinstance(type_, int)

    def test_get_trip_stop_latlons(self):
        pass  # untested

    def get_trip_stop_time_data(self):
        start_ut, end_ut = self.G.get_conservative_gtfs_time_span_in_ut()
        dsut_dict = self.G.get_tripIs_within_range_by_dsut(start_ut, end_ut)
        dsut, trip_Is = dsut_dict.items()[0]
        df = self.G.get_trip_stop_time_data(trip_Is[0], dsut)
        assert isinstance(df, pandas.DataFrame)
        columns = "departure_time_ut lat lon seq shape_break".split(" ")
        el = df.iloc[0]
        for c in columns:
            assert c in df.columns
            if c in "departure_time_ut lat lon".split(" "):
                assert isinstance(el[c], float)
            if c in "seq shape_break".split(" "):
                assert isinstance(el[c], int)



    def test_get_straight_line_transfer_distances(self):
        data = self.G.get_straight_line_transfer_distances()
        assert len(data) > 0
        a_stop_I = None
        for index, row in data.iterrows():
            assert row['from_stop_I'] is not None
            a_stop_I = row['from_stop_I']
            assert row['to_stop_I'] is not None
            assert row['d'] is not None
        data = self.G.get_straight_line_transfer_distances(a_stop_I)
        assert len(data) > 0

    def test_get_stats(self):
        d = self.G.get_stats()
        assert isinstance(d, dict)

    def test_calc_and_store_stats(self):
        self.G.meta['stats_calc_at_ut'] = None
        stats = self.G.calc_and_store_stats()
        assert isinstance(stats, dict)
        assert self.G.meta['stats_calc_at_ut'] is not None

    def test_get_median_lat_lon_of_stops(self):
        lat, lon = self.G.get_median_lat_lon_of_stops()
        assert lat != lon, "probably median lat and median lon should not be equal for any real data set"
        assert isinstance(lat, float)
        assert isinstance(lon, float)

    def test_get_centroid_of_stops(self):
        lat, lon = self.G.get_centroid_of_stops()
        assert lat != lon, "probably centroid lat and lon should not be equal for any real data set"
        assert isinstance(lat, float)
        assert isinstance(lon, float)

    def test_get_conservative_gtfs_time_span_in_ut(self):
        start_ut, end_ut = self.G.get_conservative_gtfs_time_span_in_ut()
        start_dt = datetime.datetime(2007, 1, 1)
        start_ut_comp = self.G.unlocalized_datetime_to_ut_seconds(start_dt)
        end_dt = datetime.datetime(2010, 12, 31)
        end_ut_comp = self.G.unlocalized_datetime_to_ut_seconds(end_dt) + (28 * 3600)
        assert start_ut == start_ut_comp
        assert end_ut == end_ut_comp

    def test_write_stats_as_csv(self):
        import tempfile as temp
        import pandas as pd

        testfile = temp.NamedTemporaryFile(mode='w+b')

        self.G.write_stats_as_csv(testfile.name)
        df = pd.read_csv(testfile.name)
        print 'len is ' + str(len(df))
        assert len(df) == 1

        self.G.write_stats_as_csv(testfile.name)
        df = pd.read_csv(testfile.name)
        assert len(df) == 2
        testfile.close()


        # def test_get_events_by_tripI_and_dsut(self):
        #     # OLD CODE:
        #     #
        #     # Original query data:
        #     # """
        #     #     select stop_I, dep_time_ds, arr_time_ds from stop_times JOIN stops USING(stop_I) where (trip_I = 1041) AND (dep_time_ds > 59200) AND (arr_time_ds < 59580) LIMIT 10;
        #     # stop_I|dep_time_ds|arr_time_ds
        #     # 217|59220|59220
        #     # 215|59280|59280
        #     # 213|59340|59340
        #     # 211|59460|59460
        #     # 235|59520|59520
        #     #     """
        #     # trip_I = 1041
        #     # day_start_ut = 1437080400
        #     # start_ut = day_start_ut + 59200
        #     # end_ut = day_start_ut + 59580
        #     # conn = db.connect_gtfs('hsl-2015-07-12')
        #     # cur = conn.cursor()
        #     # events = gtfs.get_events_by_tripI_and_dsut(cur, trip_I,
        #     #                                   day_start_ut,
        #     #                                   start_ut,
        #     #                                   end_ut)
        #     # assert isinstance(events, list)
        #     # assert len(events) > 0
        #     # event = events[0]
        #     # for key in ['from_stop', 'to_stop', 'dep_time_ut', 'arr_time_ut']:
        #     #     assert event.has_key(key), "Event does not have key: " +str(key)
        #     # assert event['from_stop'] == 217
        #     # assert event['to_stop'] == 215
        #     # assert event['dep_time_ut'] == 59220+day_start_ut
        #     # assert event['arr_time_ut'] == 59280+day_start_ut
        #     #
        #     # day_start_wrong_day_ut = 1438300800
        #     # start_ut = day_start_wrong_day_ut + 59200
        #     # end_ut = day_start_wrong_day_ut + 59580
        #     # events = gtfs.get_events_by_tripI_and_dsut(cur, trip_I,
        #     #                                   day_start_wrong_day_ut,
        #     #                                   start_ut,
        #     #                                   end_ut)
        #     # assert len(events) == 0
        #     pass  # untested
        #
        # def test_tripI_takes_place_on_dsut(self):
        #     # OLD CODE:
        #     #     conn = db.connect_gtfs('hsl-2015-07-12')
        #     #     cur = conn.cursor()
        #     #     trip_I = 1041
        #     #     day_start_false = 1438300800
        #     #     day_start_true = 1437080400
        #     #     assert gtfs.tripI_takes_place_on_dsut(cur, trip_I, day_start_true)
        #     #     assert not gtfs.tripI_takes_place_on_dsut(cur, trip_I, day_start_false)
        #     pass  # untested
        #
        # def test_get_tripIs_from_stopI_within_time_range(self):
        #     # OLD CODE:
        #     # def test_get_trips_from_stop():
        #     #     conn = db.connect_gtfs('hsl-2015-07-12')
        #     #     cur = conn.cursor()
        #     #     stop_I = 527
        #     #     day_start_ut = 1442350800
        #     #     start_ut = day_start_ut + 24299
        #     #     end_ut = day_start_ut + 24301
        #     #
        #     #     trip_Is = gtfs.get_tripIs_from_stopI_within_time_range(cur,
        #     #                                    stop_I,
        #     #                                    day_start_ut,
        #     #                                    start_ut,
        #     #                                    end_ut)
        #     #     assert len(trip_Is) == 1
        #     #     assert trip_Is[0] == 35988
        #     #
        #     pass  # untested
        #
        # def test_day_start_ut(self):
        #     #     os.environ['TZ'] = 'Europe/Helsinki' ; time.tzset()
        #     #
        #     #     ut = 1445772360  # 2015-10-25 13:26.  DST changed on this day.
        #     #     day_start = gtfs.day_start_ut(ut)
        #     #     # from datetime import datetime
        #     #     assert day_start == 1445724000.0, \
        #     #        "Wrong day start on DST backwards: %s!=%s"%(
        #     #            day_start, 1445727600.0)  # 2015-10-25 01:00
        #     pass  # untested
        #
        # def test_increment_daystart_ut_by_ndays(self):
        #     # def test_increment_daystart_ut():
        #     #     os.environ['TZ'] = 'Europe/Helsinki' ; time.tzset()
        #     #
        #     #     day0 = 1445682360.0  # 2015,10,24 13,26
        #     #     ds0 = gtfs.day_start_ut(day0)
        #     #     assert ds0 == 1445634000.0 # 2015,10,24, 0,0
        #     #     ds1 = gtfs.increment_daystart_ut_by_ndays(ds0)
        #     #     assert ds1 == 1445724000.0  # 2015,10,25, 1,0
        #     #     ds2 = gtfs.increment_daystart_ut_by_ndays(ds1)
        #     #     assert ds2 == 1445810400.0
        #     #     ds0_b = gtfs.increment_daystart_ut_by_ndays(ds2, -2) # go back two days
        #     #     assert ds0_b == ds0
        #     pass  # untested
        #
        # # def test__get_possible_day_starts(self):
        #     # def test__get_possible_day_starts():
        #     #     os.environ['TZ'] = 'UTC' ; time.tzset()
        #     #     day_start_ut = 2*24*3600
        #     #     start_ut = day_start_ut
        #     #     end_ut = start_ut+1
        #     #     max_time_overnight= 0
        #     #     # 7*3600
        #     #     day_start_times_ut, start_times_ds, end_times_ds = \
        #     #         gtfs._get_possible_day_starts(start_ut, end_ut, max_time_overnight)
        #     #     assert isinstance(day_start_times_ut, list)
        #     #     assert isinstance(start_times_ds, list)
        #     #     assert isinstance(end_times_ds, list)
        #     #     assert len(day_start_times_ut) == 1
        #     #     assert day_start_times_ut[0] == day_start_ut
        #     #     assert start_times_ds[0] == 0
        #     #     assert end_times_ds[0] == 1
        #     #
        #     #     day_start_ut = 2*24*3600
        #     #     start_ut = day_start_ut
        #     #     end_ut = start_ut+24*3600+1
        #     #     max_time_overnight= 1 # 1 second
        #     #     day_start_times_ut, start_times_ds, end_times_ds = \
        #     #         gtfs._get_possible_day_starts(start_ut, end_ut, max_time_overnight)
        #     #     assert len(day_start_times_ut) == 3
        #     #
        #     #     os.environ['TZ'] = 'Europe/Helsinki' ; time.tzset()
        #     #     day_start_ut = 1438300800 # multiple of 24*3600 (i.e. a _ds in UTC)
        #     #     start_ut = day_start_ut + 100 #24299
        #     #     end_ut = day_start_ut + 102 # 24301
        #     #     # print ut_to_datetime_str(start_ut)
        #     #     max_time_overnight = 7*60*60 # seven hours
        #     #
        #     #     day_start_times_ut, start_times_ds, end_times_ds = \
        #     #         gtfs._get_possible_day_starts(start_ut, end_ut, 0)
        #     #     assert len(day_start_times_ut) == 1
        #     #     assert day_start_times_ut[0] == 1438300800-3*3600
        #     #     assert start_times_ds[0] == 3*3600+100
        #     #     assert end_times_ds[0] == 3*3600+102
        #     #
        #     #     day_start_ut = 1438300800 # multiple of 24*3600 (i.e. a _ds in UTC)
        #     #     start_ut = day_start_ut + 24299
        #     #     end_ut = day_start_ut + 24301
        #     #     day_start_times_ut, start_times_ds, end_times_ds = \
        #     #         gtfs._get_possible_day_starts(start_ut, end_ut, 7*3600)
        #     #     assert len(day_start_times_ut) == 1
        #     #     assert day_start_times_ut[0] == 1438300800-3*3600
        #     #     assert start_times_ds[0] == 3*3600+24299
        #     #     assert end_times_ds[0] == 3*3600+24301
        #     pass  # untested
        #
        # def test_get_tripIs_within_range_by_dsut(self):
        #     pass  # untested
        #
        # def test_get_stop_info(self):
        #     stop_I = 1
        #     df = self.G.get_stop_info(stop_I=stop_I)
        #     assert isinstance(df, pandas.DataFrame)
        #
        # def test_get_transit_events_in_time_span(self):
        #     # start_ut = 1
        #     # end_ut = 2
        #     # res = self.G.get_transit_events_in_time_span(start_ut, end_ut)
        #     # assert isinstance(res, pandas.DataFrame)
        #     pass  # not properly tested"
        #     # OLD CODE:
        #     #
        #     # def test_get_events_within_range():
        #     #     os.environ['TZ'] = 'Europe/Helsinki' ; time.tzset()
        #     #     conn = db.connect_gtfs('hsl-2015-07-12')
        #     #     day_start_ut = 1438300800 # multiple of 24*3600 (i.e. a _ds in UTC)
        #     #     start_ut = 1438300800 + 24299
        #     #     end_ut = 1438300800 + 24301
        #     #     event_data = gtfs.get_transit_events_in_time_span(
        #     #                     conn, start_ut, end_ut)
        #     #     assert len(event_data['trip_I']) == 14070
        #     #     n_events_1 = len(event_data['trip_I'])
        #     #     # print ut_to_utc_datetime_str(end_ut)
        #     #
        #     #
        #     #     conn = db.connect_gtfs('hsl-2015-07-12')
        #     #     day_start_ut = 1438300800 # multiple of 24*3600 (i.e. a _ds in UTC)
        #     #     start_ut = 1438300800 + 24299
        #     #     end_ut = 1438300800 + 24301+3600
        #     #     event_data = gtfs.get_transit_events_in_time_span(
        #     #                     conn, start_ut, end_ut)
        #     #     # print ut_to_utc_datetime_str(end_ut)
        #     #     # print len(event_data)
        #     #     assert len(event_data['trip_I']) == 14070
        #     #     n_events_2 = len(event_data['trip_I'])
        #     #     print len(event_data)
        #     #     assert n_events_1 < n_events_2